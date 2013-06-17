#=========================================================================
# SimulationTool.py
#=========================================================================
# Tool for simulating MTL models.
#
# This module contains classes which construct a simulator given a MTL model
# for execution in the python interpreter.

import pprint
import collections
import inspect
import copy
import warnings

from sys         import flags
from SignalValue import SignalValue
from ast_visitor import DetectLoadsAndStores, get_method_ast

#-------------------------------------------------------------------------
# SimulationTool
#-------------------------------------------------------------------------
# User visible class implementing a tool for simulating MTL models.
#
# This class takes a MTL model instance and creates a simulator for execution
# in the python interpreter.
class SimulationTool( object ):

  #-----------------------------------------------------------------------
  # __init__
  #-----------------------------------------------------------------------
  # Construct a simulator based on a MTL model.
  def __init__( self, model ):

    # Check that the model has been elaborated
    if not model.is_elaborated():
      raise Exception( "cannot initialize {0} tool.\n"
                       "Provided model has not been elaborated yet!!!"
                       "".format( self.__class__.__name__ ) )

    self.model              = model
    self._nets              = []
    self._sequential_blocks = []
    self._register_queue    = []
    self._event_queue       = collections.deque()
    self._event_queue_set   = set()
    #self._svalue_callbacks  = collections.defaultdict(list)
    self.ncycles            = 0
    self._current_func      = None

    # TODO: temporary hack
    self._slice_connects    = []

    # If the -O flag was passed to python, use the perf implementation
    # of cycle, otherwise use the dev version.
    self.cycle = self._perf_cycle if flags.optimize else self._dev_cycle

    # Actually construct the simulator
    self._construct_sim()

  #-----------------------------------------------------------------------
  # eval_combinational
  #-----------------------------------------------------------------------
  # Evaluates all combinational logic blocks currently in the event queue.
  def eval_combinational( self ):
    while self._event_queue:
      self._current_func = func = self._event_queue.pop()
      self._event_queue_set.discard( func )
      #self.pstats.add_eval_call( func, self.num_cycles )
      try:
        func()
        self._current_func = None
      except TypeError:
        # TODO: can we catch this at static elaboration?
        raise Exception("Concurrent block '{}' must take no parameters!\n"
                        "file: {}\n"
                        "line: {}\n"
                        "".format( func.func_name,
                                   func.func_code.co_filename,
                                   func.func_code.co_firstlineno ) )

  #-----------------------------------------------------------------------
  # cycle
  #-----------------------------------------------------------------------
  # Advances the simulator by a single clock cycle, executing all
  # sequential @tick and @posedge_clk blocks defined in the design, as
  # well as any @combinational blocks that have been added to the event
  # queue.
  #
  # Note: see _debug_cycle and _perf_cycle for actual implementations.
  def cycle( self ):
    pass

  #-----------------------------------------------------------------------
  # _debug_cycle
  #-----------------------------------------------------------------------
  # Implementation of cycle() for use during develop-test-debug loops.
  def _dev_cycle( self ):
    # Call all events generated by input changes
    self.eval_combinational()

    # TODO: Hacky auto clock generation
    #if self.vcd:
    #  print >> self.o, "#%s" % (10 * self.num_cycles)
    self.model.clk.value = 0

    #if self.vcd:
    #  print >> self.o, "#%s" % ((10 * self.num_cycles) + 5)
    self.model.clk.value = 1

    # Call all rising edge triggered functions
    for func in self._sequential_blocks:
      func()

    # Then flop the shadow state on all registers
    while self._register_queue:
      reg = self._register_queue.pop()
      reg.flop()

    # Call all events generated by synchronous logic
    self.eval_combinational()

    # Increment the simulator cycle count
    self.ncycles += 1

  #-----------------------------------------------------------------------
  # _perf_cycle
  #-----------------------------------------------------------------------
  # Implementation of cycle() for use when benchmarking models.
  def _perf_cycle( self ):

    # Call all events generated by input changes
    self.eval_combinational()

    # Call all rising edge triggered functions
    for func in self._sequential_blocks:
      func()

    # Then flop the shadow state on all registers
    while self._register_queue:
      reg = self._register_queue.pop()
      reg.flop()

    # Call all events generated by synchronous logic
    self.eval_combinational()

    # Increment the simulator cycle count
    self.ncycles += 1

  #-----------------------------------------------------------------------
  # reset
  #-----------------------------------------------------------------------
  # Sets the reset signal high and cycles the simulator.
  def reset( self ):
    self.model.reset.v = 1
    self.cycle()
    self.cycle()
    self.model.reset.v = 0

  #-----------------------------------------------------------------------
  # print_line_trace
  #-----------------------------------------------------------------------
  # Print cycle number and line trace of model.
  def print_line_trace( self ):
    print "{:>3}:".format( self.ncycles ), self.model.line_trace()

  #-----------------------------------------------------------------------
  # add_event
  #-----------------------------------------------------------------------
  # Add an event to the simulator event queue for later execution.
  #
  # This function will check if the written SignalValue instance has any
  # registered events (functions decorated with @combinational), and if
  # so, adds them to the event queue.
  def add_event( self, signal_value ):
    # TODO: debug_event
    #print "    ADDEVENT: VALUE", signal_value.v,
    #print signal_value in self._svalue_callbacks,
    #print [x.fullname for x in signal_value._debug_signals],
    #print self._svalue_callbacks[signal_value]

    #if signal_value in self._svalue_callbacks:
    #  funcs = self._svalue_callbacks[signal_value]
    #  for func in funcs:
    #    if func != self._current_func and func not in self._event_queue_set:
    #      self._event_queue.appendleft( func )
    #      self._event_queue_set.add( func )

    for func in signal_value._callbacks:
      if func != self._current_func and func not in self._event_queue_set:
        self._event_queue.appendleft( func )
        self._event_queue_set.add( func )

  #-----------------------------------------------------------------------
  # _construct_sim
  #-----------------------------------------------------------------------
  # Construct a simulator for the provided model.
  def _construct_sim( self ):
    self._create_nets( self.model )
    self._insert_signal_values()
    self._register_decorated_functions( self.model )
    self._create_slice_callbacks()

  #-----------------------------------------------------------------------
  # _create_nets
  #-----------------------------------------------------------------------
  # Generate nets describing structural connections in the model.  Each
  # net describes a set of Signal objects which have been interconnected,
  # either directly or indirectly, by calls to connect().
  def _create_nets( self, model ):

    # DEBUG
    #print 70*'-'
    #print "Model:", model
    #print "Ports:"
    #pprint.pprint( model.get_ports(), indent=3 )
    #print "Submodules:"
    #pprint.pprint( model.get_submodules(), indent=3 )

    #def a_printer( some_set ):
    #  return [ x.parent.name + '.' + x.name for x in some_set ]
    #t = [ a_printer( [ x.src_node, x.dest_node] ) for x in model.get_connections() ]
    #print "Connections:"
    #pprint.pprint( model.get_connections(), indent=3 )
    #pprint.pprint( t, indent=3 )

    # Utility function to collect all the Signal type objects (ports,
    # wires, constants) in the model.
    def collect_signals( model ):
      signals = set( model.get_ports() + model.get_wires() )
      for m in model.get_submodules():
        signals.update( collect_signals( m ) )
      return signals

    signals = collect_signals( model )

    # Utility function to filter only supported connections: ports, and
    # wires.  No slices or Constants.
    def valid_connection( c ):
      if c.src_slice != None or c.dest_slice != None:
        # TEMPORARY HACK, remove slice connections from connections?
        self._slice_connects.append ( c )
        return False
      else:
        return True

    # Iterative Depth-First-Search algorithm, borrowed from Listing 5-5
    # in 'Python Algorithms': http://www.apress.com/9781430232377/
    def iter_dfs( s ):
      S, Q = set(), []
      Q.append( s )
      while Q:
        u = Q.pop()
        if u in S: continue
        S.add( u )
        connected_signals = [ x.other( u ) for x in u.connections
                              if valid_connection( x ) ]
        Q.extend( connected_signals )
        #yield u
      return S

    # Initially signals contains all the Signal type objects in the
    # model.  We perform a depth-first search on the connections of each
    # Signal object, and remove connected objects from the signals set.
    # The result is a collection of nets describing structural
    # connections in the design. Each independent net will later be
    # transformed into a single SignalValue object.
    while signals:
      s = signals.pop()
      net = iter_dfs( s )
      for i in net:
        #if i is not s:
        #  signals.remove( i )
        signals.discard( i )
      self._nets.append( net )

  #-----------------------------------------------------------------------
  # _insert_signal_values
  #-----------------------------------------------------------------------
  # Transform each net into a single SignalValue object. Model attributes
  # currently referencing Signal objects will be modified to reference
  # the SignalValue object of their associated net instead.
  def _insert_signal_values( self ):

    # DEBUG
    #print
    #print "NODE SETS"
    #for set in self._nets:
    #  print '    ', [ x.parent.name + '.' + x.name for x in set ]

    # Utility functions which create SignalValue callbacks.

    def create_comb_update_cb( sim, svalue ):
      def notify_sim_comb_update():
        sim.add_event( svalue )
      return notify_sim_comb_update

    def create_seq_update_cb( sim, svalue ):
      def notify_sim_seq_update():
        sim._register_queue.append( svalue )
      return notify_sim_seq_update

    # Each grouping represents a single SignalValue object. Perform a swap
    # so that all attributes currently pointing to Signal objects in this
    # grouping instead point to the SignalValue.
    for group in self._nets:

      # Get an element out of the set and use it to determine the bitwidth
      # of the net, needed to create a properly sized SignalValue object.
      # TODO: no peek() so have to pop() then reinsert it! Another way?
      # TODO: what about BitStructs?
      temp = group.pop()
      group.add( temp )
      svalue = temp.msg_type
      # TODO: should this be visible to sim?
      svalue._shadow_value = copy.copy( svalue )
      #svalue._debug_signals = group

      # Add a callback to the SignalValue so that the simulator is notified
      # whenever it's value changes.
      # TODO: Currently all SignalValues get both a comb and seq update
      #       callback.  Really should only need one or the other, and
      #       name it notify_sim().
      svalue.notify_sim_comb_update  = create_comb_update_cb( self, svalue )
      svalue.notify_sim_seq_update   = create_seq_update_cb ( self, svalue )
      svalue.notify_sim_slice_update = svalue.notify_sim_comb_update
      svalue._shadow_value.notify_sim_slice_update = svalue.notify_sim_seq_update

      # Modify model attributes currently referencing Signal objects to
      # reference SignalValue objects instead.
      # TODO: hacky based on [idx], fix?
      for x in group:
        # Set the value of the SignalValue object if we encounter a
        # constant (check for Constant object instead?)
        if isinstance( x._signalvalue, int ):
          svalue.write( x._signalvalue )
          svalue.constant = True
        # Handle Lists of Ports
        elif '[' in x.name:
          name, idx = x.name.strip(']').split('[')
          x.parent.__dict__[ name ][ int( idx ) ] = svalue
        # Handle Normal Ports
        else:
          x.parent.__dict__[ x.name ] = svalue

        # Also give signals a pointer to the SignalValue object.
        # (Needed for VCD tracing and slice logic generator).
        x._signalvalue = svalue

  #-----------------------------------------------------------------------
  # _register_decorated_functions
  #-----------------------------------------------------------------------
  # Register all decorated @tick, @posedge_clk, and @combinational
  # functions with the simulator.  Sequential logic blocks get called
  # any time cycle() is called, combinational logic blocks are registered
  # with SignalValue objects and get added to the event queue as values
  # change.
  def _register_decorated_functions( self, model ):

    # Add all cycle driven functions
    self._sequential_blocks.extend( model._tick_blocks )
    self._sequential_blocks.extend( model._posedge_clk_blocks )

    # Utility function to turn attributes/names acquired from the ast
    # into Python objects
    # TODO: should never use eval... but this is easy
    # TODO: how to handle when self is neither 's' nor 'self'?
    # TODO: how to handle temps!
    def name_to_object( name ):
      self = s = model
      if '[?]' in name:
        name, extra = name.split('[?]')
      # TODO: hacky way to account for indexing lists
      elif name.endswith( '.uint' ):
        name = name.rstrip( '.uint' )
      try:
        x = eval( name )
        if isinstance( x, (SignalValue, list) ): return x
        else:                                    raise NameError
      except NameError:
        warnings.warn( "Cannot add variable '{}' to sensitivity list."
                       "".format( name ), Warning )
        return None

    # Get the sensitivity list of each event driven (combinational) block
    # TODO: do before or after we swap value nodes?
    for func in model._combinational_blocks:
      tree = get_method_ast( func )
      loads, stores = DetectLoadsAndStores().enter( tree )
      for x in loads:
        obj = name_to_object( x )
        if   isinstance( obj, list ):
          model._newsenses[ func ].extend( obj )
        elif isinstance( obj, SignalValue ):
          model._newsenses[ func ].append( obj )

    # Iterate through all @combinational decorated function names we
    # detected, retrieve their associated function pointer, then add
    # entries for each item in the function's sensitivity list to
    # svalue_callbacks
    # TODO: merge this code with above to reduce mem of data structures?
    for func_ptr, sensitivity_list in model._newsenses.items():
      for signal_value in sensitivity_list:
        #self._svalue_callbacks[ signal_value ].append( func_ptr )
        signal_value.register_callback( func_ptr )
        # Prime the simulation by putting all events on the event_queue
        # This will make sure all nodes come out of reset in a consistent
        # state. TODO: put this in reset() instead?
        if func_ptr not in self._event_queue_set:
          self._event_queue.appendleft( func_ptr )
          self._event_queue_set.add( func_ptr )

    # Recursively perform for submodules
    for m in model.get_submodules():
      self._register_decorated_functions( m )

  #-----------------------------------------------------------------------
  # _create_slice_callbacks
  #-----------------------------------------------------------------------
  # All ConnectionEdges that contain bit slicing need to be turned into
  # combinational blocks.  This significantly simplifies the connection
  # graph update logic.
  def _create_slice_callbacks( self ):

    # Utility function to create our callback
    def create_slice_cb_closure( c ):
      src       = c.src_node._signalvalue
      dest      = c.dest_node._signalvalue
      src_addr  = c.src_slice  if c.src_slice  != None else slice( None )
      dest_addr = c.dest_slice if c.dest_slice != None else slice( None )
      def slice_cb():
        dest.v[ dest_addr ] = src.v[ src_addr ]
      return slice_cb

    for c in self._slice_connects:
      src = c.src_node._signalvalue
      # If slice is connect to a Constant, don't create a callback.
      # Just write the constant value now.
      if isinstance( src, int ):
        dest      = c.dest_node._signalvalue
        dest_addr = c.dest_slice if c.dest_slice != None else slice( None )
        dest.v[ dest_addr ] = src
      # If slice is connected to another Signal, create a callback
      # and put it on the combinational event queue.
      else:
        func_ptr = create_slice_cb_closure( c )
        signal_value = c.src_node._signalvalue
        #self._svalue_callbacks[ signal_value ].append( func_ptr )
        signal_value.register_callback( func_ptr )
        self._event_queue.appendleft( func_ptr )
        self._event_queue_set.add( func_ptr )

