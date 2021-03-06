#=========================================================================
# ast_typer.py
#=========================================================================
# Create a simplified representation of the Python AST for help with
# source to source translation.

from __future__ import print_function

import ast, _ast
import re

from ...datatypes.Bits import Bits
from ...model.signals  import InPort, OutPort

#-------------------------------------------------------------------------
# TypeAST
#-------------------------------------------------------------------------
# ASTTransformer which uses type information to simplify the AST:
#
# - clears references to the module
# - clears the decorator, attaches relevant notation to func instead
# - removes Index nodes
# - replaces Name nodes with Self if they reference the self object
# - replaces Name nodes with Temp if they reference a local temporary
# - replaces Subscript nodes with BitSlice if they reference a Bits
#   or BitStruct object
# - replaces Subscript nodes with ArrayIndex if they reference a list
# - attaches object references to each node
# - removes '.next', '.value', '.n', and '.v' Attribute nodes on Ports
#
# TODO: fix ctx references on newly created nodes
#
class TypeAST( ast.NodeTransformer ):

  def __init__( self, model, func ):
    self.model       = model
    self.func        = func
    self.closed_vars = get_closure_dict( func )
    self.current_obj = None

  #-----------------------------------------------------------------------
  # visit_Module
  #-----------------------------------------------------------------------
  def visit_Module( self, node ):
    # visit children
    self.generic_visit( node )

    # copy the function body, delete module references
    return ast.copy_location( node.body[0], node )

  #-----------------------------------------------------------------------
  # visit_FunctionDef
  #-----------------------------------------------------------------------
  def visit_FunctionDef( self, node ):
    # visit children
    self.generic_visit( node )

    # TODO: add annotation to self.func based on decorator type
    #dec = node.decorator_list[0].attr

    # create a new FunctionDef node that deletes the decorators
    #new_node = ast.FunctionDef( name=node.name, args=node.args,
    #                            body=node.body, decorator_list=)

    #return ast.copy_location( new_node, node )
    return node

  #-----------------------------------------------------------------------
  # visit_Attribute
  #-----------------------------------------------------------------------
  def visit_Attribute( self, node ):
    self.generic_visit( node )

    # TODO: handle self.current_obj == None.  These are temporary
    #       locals that we should check to ensure their types don't
    #       change!

    if self.current_obj:
      try :
        x = self.current_obj.getattr( node.attr )
        self.current_obj.update( node.attr, x )
      except AttributeError:
        if node.attr in ['next', 'value', 'n', 'v']:
          node.value.ctx = node.ctx  # Update the Load/Store information
          return node.value
        else:
          raise Exception("Error: Unknown attribute for this object: {}"
                          .format( node.attr ) )

    node._object = self.current_obj.inst if self.current_obj else None

    return node

  #-----------------------------------------------------------------------
  # visit_Name
  #-----------------------------------------------------------------------
  def visit_Name( self, node ):

    # If the name is not in closed_vars, it is a local temporary
    if   node.id not in self.closed_vars:
      new_node = Temp( id=node.id )
      new_obj  = None

    # If the name points to the model, this is a reference to self (or s)
    elif self.closed_vars[ node.id ] is self.model:
      new_node = Self( id=node.id )
      new_obj  = PyObj( '', self.closed_vars[ node.id ] )

    # Otherwise, we have some other variable captured by the closure...
    # TODO: should we allow this?
    else:
      new_node = node
      new_obj  = PyObj( node.id, self.closed_vars[ node.id ] )

    # Store the new_obj
    self.current_obj = new_obj
    node._object = self.current_obj.inst if self.current_obj else None

    # Return the new_node
    return ast.copy_location( new_node, node )

  #-----------------------------------------------------------------------
  # visit_Subscript
  #-----------------------------------------------------------------------
  def visit_Subscript( self, node ):

    # Visit the object being sliced
    new_value = self.visit( node.value )

    # Visit the index of the slice; stash and restore the current_obj
    stash = self.current_obj
    self.current_obj = None
    new_slice = self.visit( node.slice )
    self.current_obj = stash

    # If current_obj not initialized, it is a local temp. Don't replace.
    if   not self.current_obj:
      new_node = _ast.Subscript( value=new_value, slice=new_slice, ctx=node.ctx )
    # If current_obj is a Bits object, replace with a BitSlice node.
    elif isinstance( self.current_obj.inst, (Bits, InPort, OutPort) ):
      new_node = BitSlice( value=new_value, slice=new_slice, ctx=node.ctx )
    # If current_obj is a list object, replace with an ArrayIndex node.
    elif isinstance( self.current_obj.inst, list ):
      new_node = ArrayIndex( value=new_value, slice=new_slice, ctx=node.ctx )
      # TODO: Want to do this for lists, but can't add attribute
      #       handling in translation instead
      #self.current_obj.inst.name = self.current_obj.inst[0].name.split('[')[0]
    # Otherwise, throw an exception
    else:
      print( self.current_obj )
      raise Exception("Unknown type being subscripted!")

    # Update the current_obj to contain the obj returned by subscript
    # TODO: check that type of all elements in item are identical
    # TODO: won't work for lists that are initially empty
    # TODO: what about lists that initially contain None?
    if self.current_obj:
      self.current_obj.update( '[]', self.current_obj.inst[0] )
    node._object = self.current_obj.inst if self.current_obj else None

    return ast.copy_location( new_node, node )

  #-----------------------------------------------------------------------
  # visit_Index
  #-----------------------------------------------------------------------
  def visit_Index( self, node ):
    # Remove Index nodes, they seem pointless
    child = self.visit( node.value )
    return ast.copy_location( child, node )

  #-----------------------------------------------------------------------
  # visit_Call
  #-----------------------------------------------------------------------
  # Specially handle certain function calls
  def visit_Call( self, node ):
    # func, args, keywords, starargs, kwargs
    # Check that this is just a normal function call, not something weird

    self.generic_visit( node )

    if node.func.id == 'range':
      if   len( node.args ) == 1:
        start = _ast.Num( n=0 )
        stop  = node.args[0]
        step  = _ast.Num( n=1 )
      elif len( node.args ) == 2:
        start = node.args[0]
        stop  = node.args[1]
        step  = _ast.Num( n=1 ) # TODO: should be an expression
      elif len( node.args ) == 3:
        start = node.args[0]
        stop  = node.args[1]
        step  = node.args[2]
      else:
        raise Exception("Invalid # of arguments to range function!")

      new_node = _ast.Slice( lower=start, upper=stop, step=step )

    else:
      new_node = node

    return ast.copy_location( new_node, node )

#------------------------------------------------------------------------
# PyObj
#------------------------------------------------------------------------
class PyObj( object ):
  def __init__( self, name, inst ):
    self.name  = name
    self.inst  = inst
  def update( self, name, inst ):
    self.name += name
    self.inst  = inst
  def getattr( self, name ):
    return getattr( self.inst, name )
  def __repr__( self ):
    return "PyObj( name={} inst={} )".format( self.name, type(self.inst) )


#------------------------------------------------------------------------
# get_closure_dict
#------------------------------------------------------------------------
# http://stackoverflow.com/a/19416942
def get_closure_dict( fn ):
  closure_objects = [c.cell_contents for c in fn.func_closure]
  return dict( zip( fn.func_code.co_freevars, closure_objects ))

#------------------------------------------------------------------------
# ArrayIndex
#------------------------------------------------------------------------
class ArrayIndex( _ast.Subscript ):
  pass

#------------------------------------------------------------------------
# BitSlice
#------------------------------------------------------------------------
class BitSlice( _ast.Subscript ):
  pass

#------------------------------------------------------------------------
# Self
#------------------------------------------------------------------------
# New AST Node for references to self. Based on Name node.
class Self( _ast.Name ):
  pass

#------------------------------------------------------------------------
# Temp
#------------------------------------------------------------------------
# New AST Node for local temporaries. Based on Name node.
class Temp( _ast.Name ):
  pass

