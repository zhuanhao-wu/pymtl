from model import *

class ConstantWires(Model):
  def __init__(self, bits):
    self.out0  = OutPort(8)
    self.out1  = OutPort(8)
    self.wire1 = Wire(8)
    self.wire2 = Wire(8)
    self.wire3 = Wire(1)

    connect( self.out0,  2 )
    connect( self.wire1, 4 )
    connect( self.wire1, self.out1 )
    connect( self.wire2, 6 )
    connect( self.wire3, 1 )

class SensitivityList(Model):
  def __init__(self):
    self.in_   = InPort(8)
    self.outA  = OutPort(8)
    self.wireB = Wire(8)
    self.outB  = OutPort(8)
    self.outC1 = OutPort(8)
    self.outC2 = OutPort(8)
    self.outD1 = OutPort(8)
    self.outD2 = OutPort(8)

  @combinational
  def combA( self ):
    self.outA.value = self.in_.value

  @combinational
  def combB( self ):
    self.outB.value = self.wireB.value

  @combinational
  def combC( self ):
    self.outC2.value = self.outC1.value

  @combinational
  def combD( self ):
    self.outD2.value = self.outD1.value

  @posedge_clk
  def seq_logic( self ):
    self.wireB.next = self.in_.value
    self.outC1.next = self.in_.value
    if self.reset.value == 1:
      self.outD1.next = 0
    else:
      self.outD1.next = self.outD1.value + 1


class Rotator(Model):
  def __init__(self, bits):
    # Ports
    self.inp = [ InPort(1)  for x in xrange(bits) ]
    self.out = [ OutPort(1) for x in xrange(bits) ]
    # Connections
    for i in xrange(bits - 1):
      connect( self.inp[i], self.out[i+1] )
    connect( self.inp[-1], self.out[0] )

# TODO: broken!
#class RotatorSlice(Model):
#  def __init__(self, bits):
#    # Ports
#    self.inp = InPort(bits)
#    self.out = OutPort(bits)
#    # Connections
#    for i in xrange(bits - 1):
#      self.inp[i] <> self.out[i+1]
#    self.inp[-1] <> self.out[0]

class SimpleSplitter(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = [ OutPort(1) for x in xrange(bits) ]
    # Connections
    for i in xrange(bits):
      connect( self.out[i], self.inp[i] )


class ComplexSplitter(Model):
  def __init__(self, bits, groupings):
    # Port Definitions
    self.inp = InPort(bits)
    self.out = [ OutPort(groupings) for x in xrange(0, bits, groupings) ]
    # Connections
    outport_num = 0
    for i in xrange(0, bits, groupings):
      connect( self.out[outport_num], self.inp[i:i+groupings] )
      outport_num += 1


class SimpleMerger(Model):
  def __init__(self, bits):
    # Port Definitions
    self.inp = [ InPort(1) for x in xrange(bits) ]
    self.out = OutPort(bits)
    # Connections
    for i in xrange(bits):
      connect( self.out[i], self.inp[i] )


class ComplexMerger(Model):
  def __init__(self, bits, groupings):
    # Port Definitions
    self.inp = [ InPort(groupings) for x in xrange(0, bits, groupings) ]
    self.out = OutPort(bits)
    # Connections
    inport_num = 0
    for i in xrange(0, bits, groupings):
      connect( self.out[i:i+groupings], self.inp[inport_num] )
      inport_num += 1


class OneWire(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = OutPort(bits)
    # Connections
    connect( self.inp, self.out )


class OneWireWrapped(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = OutPort(bits)
    # Submodules
    # TODO: cannot use keyword "wire" for variable names when converting
    #       To! Check for this?
    self.wire0 = OneWire(bits)
    # Connections
    connect( self.inp, self.wire0.inp )
    connect( self.out, self.wire0.out )


class Register(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = OutPort(bits)
  @posedge_clk
  def tick(self):
    self.out.next = self.inp.value

class RegisterReset(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = OutPort(bits)
  @posedge_clk
  def tick(self):
    if self.reset.value:
      self.out.next = 0
    else:
      self.out.next = self.inp.value

class RegisterWrapper(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = OutPort(bits)
    # Submodules
    # TODO: cannot use keyword "reg" for variable names when converting
    #       To! Check for this?
    self.reg0 = Register(bits)
    # Connections
    connect( self.inp, self.reg0.inp )
    connect( self.out, self.reg0.out )


class RegisterChain(Model):
  def __init__(self, bits):
    # Ports
    self.inp = InPort(bits)
    self.out = OutPort(bits)
    # Submodules
    self.reg1 = Register(bits)
    self.reg2 = Register(bits)
    self.reg3 = Register(bits)
    # Connections
    connect( self.inp     , self.reg1.inp )
    connect( self.reg1.out, self.reg2.inp )
    connect( self.reg2.out, self.reg3.inp )
    connect( self.reg3.out, self.out      )


class RegisterSplitter(Model):
  def __init__(self, bits):
    groupings = 2
    # Ports
    self.inp = InPort(bits)
    self.out = [ OutPort(groupings) for x in xrange(0, bits, groupings) ]
    # Submodules
    self.reg0  = Register(bits)
    self.split = ComplexSplitter(bits, groupings)
    # Connections
    connect( self.inp     , self.reg0.inp  )
    connect( self.reg0.out, self.split.inp )
    for i, x in enumerate(self.out):
      connect( self.split.out[i], x )

class FanOutOne(Model):
  def __init__(self, bits):
    # Ports
    self.inp  = InPort(bits)
    self.out1 = OutPort(bits)
    self.out2 = OutPort(bits)
    self.out3 = OutPort(bits)
    # Submodules
    self.reg0 = Register(bits)
    # Connections
    connect( self.inp     , self.reg0.inp )
    connect( self.reg0.out, self.out1     )
    connect( self.reg0.out, self.out2     )
    connect( self.reg0.out, self.out3     )

class FanOutTwo(Model):
  def __init__(self, bits):
    # Ports
    self.inp  = InPort(bits)
    self.out1 = OutPort(bits)
    self.out2 = OutPort(bits)
    self.out3 = OutPort(bits)
    # Submodules
    self.reg0 = Register(bits)
    self.reg1 = Register(bits)
    self.reg2 = Register(bits)
    self.reg3 = Register(bits)
    # Connections
    connect( self.inp     , self.reg0.inp )
    connect( self.reg0.out, self.reg1.inp )
    connect( self.reg0.out, self.reg2.inp )
    connect( self.reg0.out, self.reg3.inp )
    connect( self.reg1.out, self.out1     )
    connect( self.reg2.out, self.out2     )
    connect( self.reg3.out, self.out3     )


class FullAdder(Model):
  def __init__(self):
    # Ports
    self.in0  = InPort (1)
    self.in1  = InPort (1)
    self.cin  = InPort (1)
    self.sum  = OutPort(1)
    self.cout = OutPort(1)

  @combinational
  def logic(self):
    a = self.in0.value
    b = self.in1.value
    c = self.cin.value
    self.sum.value  = (a ^ b) ^ c
    self.cout.value = (a & b) | (a & c) | (b & c)


class RippleCarryAdder(Model):
  def __init__(self, bits):
    # Ports
    self.in0 = InPort (bits)
    self.in1 = InPort (bits)
    self.sum = OutPort(bits)
    # Submodules
    self.adders = [ FullAdder() for i in xrange(bits) ]
    # Connections
    for i in xrange(bits):
      connect( self.adders[i].in0, self.in0[i] )
      connect( self.adders[i].in1, self.in1[i] )
      connect( self.adders[i].sum, self.sum[i] )
    for i in xrange(bits-1):
      connect( self.adders[i+1].cin, self.adders[i].cout )
    connect( self.adders[0].cin, 0 )


class Incrementer(Model):
  def __init__(self):
    # Ports
    self.inp  = InPort(32)
    self.out  = OutPort(32)

  @combinational
  def logic(self):
    self.out.value = self.inp.value + 1

class Counter(Model):
  def __init__(self, max=None):
    # Ports
    self.clear = InPort(1)
    self.count = OutPort(32)
    # Params
    self.max   = max

  @posedge_clk
  def logic(self):
    if self.clear.value:
      self.count.next = 0
    elif self.count.value == self.max:
      self.count.next = 0
    else:
      self.count.next = self.count.value + 1

class CountIncr(Model):
  def __init__(self, max=None):
    # Ports
    self.clear = InPort(1)
    self.count = OutPort(32)
    # Submodules
    self.incr  = Incrementer()
    self.cntr  = Counter(max)
    # Connections
    connect( self.clear     , self.cntr.clear )
    connect( self.cntr.count, self.incr.inp   )
    connect( self.incr.out  , self.count      )

class RegIncr(Model):
  def __init__(self):
    # Ports
    self.inp = InPort(32)
    self.out = OutPort(32)
    # Submodules
    self.reg0 = Register(32)
    self.incr = Incrementer()
    # Connections
    connect( self.inp     , self.reg0.inp )
    connect( self.reg0.out, self.incr.inp )
    connect( self.incr.out, self.out      )

class IncrReg(Model):
  def __init__(self):
    # Ports
    self.inp = InPort(32)
    self.out = OutPort(32)
    # Submodules
    self.incr = Incrementer()
    self.reg0 = Register(32)
    # Connections
    connect( self.inp     , self.incr.inp )
    connect( self.incr.out, self.reg0.inp )
    connect( self.reg0.out, self.out      )

class GCD(Model):
  def __init__(self):
    # Ports
    self.in_A    = InPort(32)
    self.in_B    = InPort(32)
    self.in_val  = InPort(1)
    self.out     = OutPort(32)
    self.out_val = OutPort(1)
    # Wires
    self.state      = Wire(2)
    self.A_reg      = Wire(32)
    self.B_reg      = Wire(32)
    self.is_A_lt_B  = Wire(1)
    self.is_B_neq_0 = Wire(1)
    # Constants
    self.IDLE   = 0
    self.ACTIVE = 1
    self.DONE   = 2

  @posedge_clk
  def tick(self):
    # State transition
    if   self.state.value == self.IDLE:
      if self.in_val.value:
        self.state.next = self.ACTIVE
    elif self.state.value == self.ACTIVE:
      if not self.is_A_lt_B.value and not self.is_B_neq_0.value:
        self.state.next = self.DONE
    elif self.state.value == self.DONE:
      self.state.next = self.IDLE

    # Set A_reg
    if   self.state.value == self.IDLE:
      self.A_reg.next = self.in_A.value
    elif self.state.value == self.ACTIVE:
      if self.is_A_lt_B.value:
        self.A_reg.next = self.B_reg.value
      elif self.is_B_neq_0.value:
        self.A_reg.next = self.A_reg.value - self.B_reg.value

    # Set B_reg
    if   self.state.value == self.IDLE:
      self.B_reg.next = self.in_B.value
    elif self.state.value == self.ACTIVE and self.is_A_lt_B.value:
        self.B_reg.next = self.A_reg.value

  @combinational
  def logic(self):
    self.is_A_lt_B.value  = (self.A_reg.value < self.B_reg.value)
    self.is_B_neq_0.value = (self.B_reg.value != 0)
    self.out_val.value    = (self.state.value == self.DONE)
    self.out.value        = self.A_reg.value

  def line_trace(self):
    sdict = { 0:'Idle', 1:'Actv', 2:'Done' }
    self.IDLE   = 0
    self.ACTIVE = 1
    self.DONE   = 2
    line  = "{0} {1} {2} ||".format( self.in_A.value.uint, self.in_B.value.uint,
                                     self.in_val.value.uint )
    line += "{0:2} {1:2} {2}".format( self.A_reg.value.uint, self.B_reg.value.uint,
                                    sdict[self.state.value.uint] )
    line += " A<B:{0} B!=0:{1}".format( self.is_A_lt_B.value.uint, self.is_B_neq_0.value.uint)
    line += "|| {0} {1}".format( self.out.value.uint, self.out_val.value.uint )
    print line


class Overflow( Model ):
  def __init__( self, W = 16 ):
    self.in0 = InPort( W )
    self.in1 = InPort( W )
    self.out = OutPort( W )
  @combinational
  def comb_logic( self ):
    self.out.value = self.in0.value - self.in1.value;

class SignExtSlice( Model ):
  def __init__( self, W = 8 ):
    self.in_ = InPort( 1 )
    self.out = OutPort( W )
    for i in range(W):
      connect( self.out[i], self.in_ )

class SignExtComb( Model ):
  def __init__( self, W = 2 ):
    self.in_ = InPort( 1 )
    self.out = OutPort( W )
    self.W = W
  @combinational
  def comb_logic( self ):
    for i in range(self.W):
      self.out[i].value = self.in_.value

class ChildModuleSensitivity1(Model):
  def __init__(self):
    # Ports
    self.in0  = InPort(32)
    self.out  = OutPort(32)
    # Submodules
    self.reg0 = Register(32)
    self.incr = Incrementer()
    # Connections
    connect( self.in0      , self.reg0.inp )
    connect( self.reg0.out , self.incr.inp )
  @combinational
  def comb_logic( self ):
    self.out.value = self.incr.out.value + 2

class ChildModuleSensitivity2(Model):
  def __init__(self):
    # Ports
    self.in0  = InPort(32)
    self.in1  = InPort(32)
    self.out  = OutPort(32)
    # Submodules
    self.reg0 = Register(32)
    self.reg1 = Register(32)
    # Connections
    connect( self.in0      , self.reg0.inp )
    connect( self.in1      , self.reg1.inp )
  @combinational
  def comb_logic( self ):
    self.out.value = self.reg0.out.value + self.reg1.out.value

class ConstantPort(Model):
  def __init__(self):
    # Ports
    self.out = OutPort(32)
    connect( self.out, 4 )

class ConstantSlice(Model):
  def __init__(self):
    # Ports
    self.out = OutPort(32)
    connect( self.out[0:16],  4 )
    connect( self.out[16:32], 8 )

class Shifter(Model):
  def __init__( self, inout_nbits = 1, shamt_nbits = 1 ):
    self.in_   = InPort  ( inout_nbits )
    self.shamt = InPort  ( shamt_nbits )
    self.out   = OutPort ( inout_nbits )

  @combinational
  def comb_logic( self ):
    self.out.value = self.in_.value << self.shamt.value


class ConstantModule(Model):
  def __init__(self):
    self.in_   = InPort  ( 8 )
    self.out   = OutPort ( 8 )

    self.shift = m = Shifter(8,2)
    connect({
      m.in_   : self.in_,
      m.shamt : 2,
      m.out   : self.out,
    })

class MultipleWrite(Model):
  def __init__(self):
    # Ports
    self.in_ = InPort(32)
    self.out = OutPort(32)
  @combinational
  def comb_logic( self ):
    self.out.value = 0
    if self.in_.value > 4:
      self.out.value = self.in_.value

from math import log, ceil
class MuxRegister( Model ):
  def __init__( s, nports, nbits ):
    s.in_ = [InPort( nbits ) for x in range( nports )]
    s.sel = InPort ( int( ceil( log( nports, 2 ) ) ))
    s.out = OutPort( nbits )
    s.mux = Wire( nbits )
  @combinational
  def comb_logic( s ):
    assert s.sel.value.uint < len( s.in_ )
    s.mux.value = s.in_[ s.sel.value.uint ].value
  @posedge_clk
  def sync_logic( s ):
    s.out.next = s.mux.value


class DemuxNoLoop( Model ):
  def __init__( s, nports, nbits ):
    s.in_ = InPort( nbits )
    s.sel = InPort ( int( ceil( log( nports, 2 ) ) ))
    s.out = [OutPort( nbits ) for x in range( nports )]
  @combinational
  def demux_logic( s ):
    s.out[ s.sel.value.uint ].value = s.in_.value
    # Workaround for sensitivity list bug (FIXED)
    #a = s.sel.value
    #s.out[ a.uint ].value = s.in_.value

class Demux( Model ):
  def __init__( s, nports, nbits ):
    s.nports = nports
    s.in_ = InPort( nbits )
    s.sel = InPort ( int( ceil( log( nports, 2 ) ) ))
    s.out = [OutPort( nbits ) for x in range( nports )]
  @combinational
  def demux_logic( s ):
    #assert s.sel.value.uint < len( s.in_ )
    for i in range( s.nports ):
      if i == s.sel.value:
        s.out[ i ].value = s.in_.value
      else:
        s.out[ i ].value = 0

class NextSlices( Model ):
  def __init__( s ):
    s.in_  = InPort ( 8 )
    s.out0 = OutPort( 8 )
    s.out1 = OutPort( 8 )
  @posedge_clk
  def seq_logic( s ):
    s.out0[0:4].next  = s.in_[4:8].value
    s.out0[4:8].next  = s.in_[0:4].value
  @combinational
  def comb_logic( s ):
    s.out1[0:4].value = s.in_[4:8].value
    s.out1[4:8].value = s.in_[0:4].value


#class RegisteredAdder1(Model):
#  def __init__(self, bits):
#    # Ports
#    self.in0 = InPort(bits)
#    self.in1 = InPort(bits)
#    self.out = OutPort(bits)
#  @posedge_clk
#  def tick(self):
#    in0 = self.in0
#    in1 = self.in1
#    out = self.out
#    out <<= in0 + in1
#
#class RegisteredAdder2(Model):
#  def __init__(self, bits):
#    # Ports
#    self.in0 = InPort(bits)
#    self.in1 = InPort(bits)
#    self.out = OutPort(bits)
#    # Submodules
#    self.sum = OneWire(bits)
#  @combinational
#  def tick(self):
#    in0 = self.in0
#    in1 = self.in1
#    sum = self.sum
#    sum <<= in0 + in1
#  @posedge_clk
#  def tick():
#    in0 = self.in0
#    in1 = self.in1
#    out = self.out
#    out <<= sum

