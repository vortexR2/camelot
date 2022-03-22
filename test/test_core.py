# -*- coding: utf-8 -*-
import copy
import os
import tempfile
import unittest

from .test_model import ExampleModelMixinCase
from camelot.core.conf import SimpleSettings, settings
from camelot.core.memento import SqlMemento, memento_change, memento_types
from camelot.core.naming import (
    AlreadyBoundException, BindingType, ConstantNamingContext, initial_naming_context, InitialNamingContext,
    NameNotFoundException, NamingContext, NamingException, UnboundException
)
from camelot.core.profile import Profile, ProfileStore
from camelot.core.qt import QtCore, py_to_variant, variant_to_py

memento_id_counter = 0

class MementoCase(unittest.TestCase, ExampleModelMixinCase):
    """test functions from camelot.core.memento
    """
    
    def setUp( self ):
        super( MementoCase, self ).setUp()
        self.setup_sample_model()
        global memento_id_counter
        custom_memento_types = memento_types + [(100, 'custom')]
        self.memento = SqlMemento( memento_types = custom_memento_types )
        memento_id_counter += 1
        self.id_counter = memento_id_counter
        self.model = 'TestMemento'

    def tearDown(self):
        self.tear_down_sample_model()

    def test_lifecycle( self ):
        memento_changes = [
            memento_change( self.model, 
                            [self.id_counter], 
                            None, 'create' ),            
            memento_change( self.model, 
                            [self.id_counter], 
                            {'name':'foo'}, 'before_update' ),
            memento_change( self.model, 
                            [self.id_counter], 
                            {'name':'bar'}, 'before_delete' ),            
            ]
        
        self.memento.register_changes( memento_changes )
        changes = list( self.memento.get_changes( self.model,
                                                  [self.id_counter],
                                                  {} ) )
        self.assertEqual( len(changes), 3 )
        
    def test_no_error( self ):
        memento_changes = [
            memento_change( None, 
                            [self.id_counter], 
                            None, None ),                     
            ]
        self.memento.register_changes( memento_changes )
        
    def test_custom_memento_type( self ):
        memento_changes = [
            memento_change( self.model, 
                            [self.id_counter], 
                            {}, 'custom' ),                     
            ]
        self.memento.register_changes( memento_changes )
        changes = list( self.memento.get_changes( self.model,
                                                  [self.id_counter],
                                                  {} ) )
        self.assertEqual( len(changes), 1 )
       
class ProfileCase(unittest.TestCase):
    """Test the save/restore and selection functions of the database profile
    """
    
    def setUp( self ):
        # Tests executed by the launcher should not use the vfinance QSettings
        QtCore.QCoreApplication.setApplicationName('camelot-tests')

    def test_profile_state( self ):
        name, host, password = u'profile_tést', u'192.168.1.1', u'top-sécrèt'
        profile = Profile( name=name, host=host, password=password )
        state = profile.__getstate__()
        # name should not be encrypted, others should
        self.assertEqual( state['profilename'], name )
        self.assertEqual( state['host'], host )
        self.assertEqual( state['pass'], password )
        new_profile = Profile(name=None)
        new_profile.__setstate__( state )
        self.assertEqual( new_profile.name, name )
        self.assertEqual( new_profile.host, host )
        self.assertEqual( new_profile.password, password )

    def test_registry_settings(self):
        # construct a profile store from application settings
        store = ProfileStore()
        store.read_profiles()
        # continue test with a profile store from file, to avoid test inference

    def test_profile_store( self ):
        handle, filename = tempfile.mkstemp()
        os.close(handle)
        store = ProfileStore(filename)
        self.assertEqual( store.read_profiles(), [] )
        self.assertEqual( store.get_last_profile(), None )
        profile_1 = Profile(u'prôfile_1')
        profile_1.dialect = u'sqlite'
        profile_2 = Profile(u'prôfile_2')
        profile_2.dialect = u'mysql'
        store.write_profiles( [profile_1, profile_2] )
        self.assertEqual( len(store.read_profiles()), 2 )
        store.set_last_profile( profile_1 )
        self.assertTrue( store.get_last_profile().name, u'prôfile_1' )
        self.assertTrue( store.get_last_profile().dialect, u'sqlite' )
        store.set_last_profile( profile_2 )
        self.assertTrue( store.get_last_profile().name, u'prôfile_2' )
        self.assertTrue( store.get_last_profile().dialect, u'mysql' )
        # os.remove(filename)

        return store

class ConfCase(unittest.TestCase):
    """Test the global configuration"""
    
    def test_import_settings(self):
        self.assertEqual( settings.get('FOO', None), None )
        self.assertRaises( AttributeError, lambda:settings.FOO )
        self.assertTrue( settings.CAMELOT_MEDIA_ROOT.endswith( 'media' ) )
        self.assertFalse( hasattr( settings, 'FOO' ) )
        
        class AdditionalSettings( object ):
            FOO = True
            
        settings.append( AdditionalSettings() )
        self.assertTrue( hasattr( settings, 'FOO' ) )
        try:
            settings.append_settings_module()
        except ImportError:
            pass
        
    def test_simple_settings(self):
        settings = SimpleSettings( 'Conceptive Engineering', 'Camelot Test')
        self.assertTrue( settings.ENGINE() )
        self.assertTrue( settings.CAMELOT_MEDIA_ROOT() )

class QtCase(unittest.TestCase):
    """Test the qt binding abstraction module
    """

    def test_variant(self):
        for obj in ['a', 5]:
            self.assertEqual(variant_to_py(py_to_variant(obj)), obj)

class AbstractNamingContextCaseMixin(object):

    context_name = None
    context_cls = None

    # Name values that should throw an invalid_name NamingException.
    invalid_names = [None, '', tuple(), ('',), (None,), ('test', ''), ('test', None)]
    valid_names = ['test', ('test',), ('first', 'second')]

    def new_context(self):
        return self.context_cls()

    def test_qualified_name(self):
        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.get_qual_name('test')
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.get_qual_name(invalid_name)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # Verify the qualified name resolution of a context concatenates its name prefix with the provid name:
        # So the qualified result should just be the composite form of the provided name.
        for valid_name in self.valid_names:
            qual_name = (*self.context_name, *(valid_name if isinstance(valid_name, tuple) else [valid_name]))
            self.assertEqual(self.context.get_qual_name(valid_name), qual_name)

    def test_resolve(self):
        # Verify general exceptions raised when resolving a name-object binding.
        # Regular behaviour should be tested in other tests throughout this case after binding.

        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.resolve('test')
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.resolve(invalid_name)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

    # Some naming contexts implementation may not implement the complete AbstractNamingContext interface,
    # so assert a NotImplementedError by default so corresponding test cases verify this.
    def test_resolve_context(self):
        with self.assertRaises(NotImplementedError):
            self.context.resolve_context('test')

    def test_bind(self):
        with self.assertRaises(NotImplementedError):
            self.context.bind('test', 1)

    def test_rebind(self):
        with self.assertRaises(NotImplementedError):
            self.context.rebind('test', 1)

    def test_bind_context(self):
        subcontext = self.new_context()
        with self.assertRaises(NotImplementedError):
            self.context.bind_context('subcontext', subcontext)

    def test_rebind_context(self):
        subcontext = self.new_context()
        with self.assertRaises(NotImplementedError):
            self.context.rebind_context('subcontext', subcontext)

    def test_unbind(self):
        with self.assertRaises(NotImplementedError):
            self.context.unbind('test')

    def test_unbind_context(self):
        with self.assertRaises(NotImplementedError):
            self.context.unbind_context('test')

class NamingContextCaseMixin(AbstractNamingContextCaseMixin):

    def test_qualified_name(self):
        super().test_qualified_name()
        # Add a subcontext to the context and verify that its qualified name resolution includes
        # the name of its associated context:
        subcontext = self.context.bind_new_context('subcontext')
        self.assertEqual(subcontext.get_qual_name('test'), (*self.context_name, 'subcontext', 'test'))

    def test_bind(self):
        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.bind('test', 1)
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.bind(invalid_name, 2)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # Test the binding of an object to the context, which should return the fully qualified binding name,
        # and verify it can be looked back up on both the context (with the bound name),
        # and on the initial context (using the returned fully qualified name).
        name, obj = 'obj1', object()
        qual_name = self.context.bind(name, obj)
        self.assertEqual(qual_name, (*self.context_name, name))
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn(name, self.context)
        self.assertIn(tuple([name]), self.context)
        self.assertEqual(self.context.resolve(name), obj)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj)

        # Verify that trying to bind again under the same name throws the appropriate exception:
        with self.assertRaises(AlreadyBoundException):
            self.context.bind(name, object())

        # Trying to bind an object using a composite name for which no subcontext binding could be found:
        name, obj = ('subcontext', 'obj2'), object()
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.bind(name, obj)
        self.assertEqual(exc.exception.name, 'subcontext')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)

        # Add a subcontext, and verify binding an object to it through the main context using the composite name:
        subcontext = self.context.bind_new_context('subcontext')
        qual_name = self.context.bind(name, obj)
        self.assertEqual(qual_name, (*self.context_name, *name))
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn(name, self.context)
        self.assertIn('obj2', subcontext)
        self.assertEqual(self.context.resolve(name), obj)
        self.assertEqual(subcontext.resolve('obj2'), obj)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj)

    def test_rebind(self):
        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.rebind('test', 1)
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.rebind(invalid_name, 2)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # Test rebinding without an existing binding, which should behave like the regular bind():
        name, obj = 'obj1', object()
        qual_name = self.context.rebind(name, obj)
        self.assertEqual(qual_name, (*self.context_name, name))
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn(name, self.context)
        self.assertIn(tuple([name]), self.context)
        self.assertEqual(self.context.resolve(name), obj)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj)

        # Rebinding again under same name now should replace
        # the binding (in contrast to the AlreadyBoundException thrown with the regular bind).
        obj2 = object()
        self.context.rebind(name, obj2)
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn(name, self.context)
        self.assertEqual(self.context.resolve(name), obj2)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj2)

        # Trying to rebind an object using a composite name for which no subcontext binding could be found:
        name, obj = ('subcontext', 'obj2'), object()
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.rebind(name, obj)
        self.assertEqual(exc.exception.name, 'subcontext')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)

        # Add a subcontext, and verify rebinding an object initially to it through the main context using the composite name:
        subcontext = self.context.bind_new_context('subcontext')
        qual_name = self.context.bind(name, obj)
        self.assertEqual(qual_name, (*self.context_name, *name))
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn(name, self.context)
        self.assertIn('obj2', subcontext)
        self.assertEqual(self.context.resolve(name), obj)
        self.assertEqual(subcontext.resolve('obj2'), obj)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj)

        # Composite rebinding under same name
        obj2 = object()
        self.context.rebind(name, obj2)
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn(name, self.context)
        self.assertEqual(self.context.resolve(name), obj2)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj2)

        # Test binding a context as a regular object to another object.
        # Context need to be bound, so bind to the initial context, and add some binding:
        context_obj = initial_naming_context.bind_new_context('context2')
        name, obj = 'test', object()
        context_obj.bind(name, obj)        
        # Then regularly bind the second context as an object to the subcontext created above:
        qual_name = subcontext.bind('context_obj', context_obj)
        self.assertEqual(qual_name, subcontext.get_qual_name('context_obj'))
        self.assertIn(qual_name, initial_naming_context)
        self.assertIn('context_obj', subcontext)
        self.assertEqual(subcontext.resolve('context_obj'), context_obj)
        self.assertEqual(initial_naming_context.resolve(qual_name), context_obj)
        # It should not be able to be resolved as a context:
        with self.assertRaises(NameNotFoundException) as exc:
            subcontext.resolve_context('context_obj')
        self.assertEqual(exc.exception.name, 'context_obj')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)
        # Verify that the added context object does not participate in the recursive resolve
        # and should throw a not found exception:
        with self.assertRaises(NameNotFoundException) as exc:
            subcontext.resolve(('context_obj', 'test'))
        self.assertEqual(exc.exception.name, 'context_obj')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)

    def test_bind_context(self):
        name, subcontext = 'subcontext', NamingContext()

        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.bind_context('subcontext', subcontext)
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.bind_context(invalid_name, subcontext)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # The passed object should be asserted to be an instance of NamingContext:
        for invalid_context in [None, '', object()]:
            with self.assertRaises(NamingException) as exc:
                self.context.bind_context(name, invalid_context)
            self.assertEqual(exc.exception.message, NamingException.Message.context_expected)

        # Test the binding of a subcontext to the context, which should return the fully qualified binding name,
        # and verify it can be looked back up on both the context (with the bound name),
        # and on the initial context (using the returned fully qualified name).
        qual_name = self.context.bind_context(name, subcontext)
        self.assertEqual(qual_name, (*self.context_name, name))
        # The qualified name should not be included in the context's contains definition as that only accounts for object bindings.
        self.assertNotIn(qual_name, initial_naming_context)
        self.assertNotIn(name, self.context)
        self.assertNotIn(tuple([name]), self.context)
        # It should however be possible to look the context back up again using the (qualified) name using resolve_context:
        self.assertEqual(self.context.resolve_context(name), subcontext)
        self.assertEqual(initial_naming_context.resolve_context(qual_name), subcontext)

        # Verify that trying to bind again under the same name throws the appropriate exception:
        with self.assertRaises(AlreadyBoundException):
            self.context.bind_context(name, NamingContext())

        # Trying to bind a subcontext using a composite name for which no subcontext binding could be found:
        name, subsubcontext = ('subcontext2', 'subsubcontext'), NamingContext()
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.bind_context(name, subsubcontext)
        self.assertEqual(exc.exception.name, 'subcontext2')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)

        # Add the subcontext, and verify binding a subcontext to it through the main context using the composite name:
        subcontext = self.context.bind_new_context('subcontext2')
        qual_name = self.context.bind_context(name, subsubcontext)
        self.assertEqual(qual_name, (*self.context_name, *name))
        self.assertNotIn(qual_name, initial_naming_context)
        self.assertNotIn(name, self.context)
        self.assertNotIn('subsubcontext', subcontext)
        self.assertEqual(self.context.resolve_context(name), subsubcontext)
        self.assertEqual(subcontext.resolve_context('subsubcontext'), subsubcontext)
        self.assertEqual(initial_naming_context.resolve_context(qual_name), subsubcontext)

    def test_rebind_context(self):
        name, subcontext = 'subcontext', NamingContext()

        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.rebind_context('subcontext', subcontext)
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.rebind_context(invalid_name, subcontext)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # The passed object should be asserted to be an instance of NamingContext:
        for invalid_context in [None, '', object()]:
            with self.assertRaises(NamingException) as exc:
                self.context.rebind_context(name, invalid_context)
            self.assertEqual(exc.exception.message, NamingException.Message.context_expected)

        # Test the rebinding of a subcontext to the context, with no existing context binding, which should behave as a regular bind_context()
        qual_name = self.context.rebind_context(name, subcontext)
        self.assertEqual(qual_name, (*self.context_name, name))
        # The qualified name should not be included in the context's contains definition as that only accounts for object bindings.
        self.assertNotIn(qual_name, initial_naming_context)
        self.assertNotIn(name, self.context)
        self.assertNotIn(tuple([name]), self.context)
        # It should however be possible to look the context back up again using the (qualified) name using resolve_context:
        self.assertEqual(self.context.resolve_context(name), subcontext)
        self.assertEqual(initial_naming_context.resolve_context(qual_name), subcontext)

        # Rebinding a context again under same name now should replace
        # the binding (in contrast to the AlreadyBoundException thrown with the regular bind_context).        
        subcontext2 = NamingContext()
        self.context.rebind_context(name, subcontext2)
        self.assertNotIn(qual_name, initial_naming_context)
        self.assertNotIn(name, self.context)
        self.assertNotIn(tuple([name]), self.context)
        self.assertEqual(self.context.resolve_context(name), subcontext2)
        self.assertEqual(initial_naming_context.resolve_context(qual_name), subcontext2)

        # Trying to rebind a subcontext using a composite name for which no subcontext binding could be found:
        name, subsubcontext = ('subcontext2', 'subsubcontext'), NamingContext()
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.rebind_context(name, subsubcontext)
        self.assertEqual(exc.exception.name, 'subcontext2')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)

        # Add the subcontext, and verify rebinding a subcontext to it through the main context using the composite name:
        subcontext = self.context.bind_new_context('subcontext2')
        qual_name = self.context.rebind_context(name, subsubcontext)
        self.assertEqual(qual_name, (*self.context_name, *name))
        self.assertNotIn(qual_name, initial_naming_context)
        self.assertNotIn(name, self.context)
        self.assertNotIn('subsubcontext', subcontext)
        self.assertEqual(self.context.resolve_context(name), subsubcontext)
        self.assertEqual(subcontext.resolve_context('subsubcontext'), subsubcontext)
        self.assertEqual(initial_naming_context.resolve_context(qual_name), subsubcontext)

    def test_unbind(self):
        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.unbind('test')
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        self.context.bind_new_context('subcontext')
        name1, obj1 = 'obj1', object()
        name2, obj2 = ('subcontext', 'obj2'), object()

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.unbind(invalid_name)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # Unbinding should fail when no existing binding was found:
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.unbind(name1)
        self.assertEqual(exc.exception.name, name1)
        self.assertEqual(exc.exception.binding_type, BindingType.named_object)
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.unbind(name2)
        self.assertEqual(exc.exception.name, name2[-1])
        self.assertEqual(exc.exception.binding_type, BindingType.named_object)

        # Add binding to be able to verify unbinding it:
        qual_name_1 = self.context.bind(name1, obj1)
        self.assertIn(name1, self.context)
        self.assertIn(qual_name_1, initial_naming_context)
        self.assertEqual(self.context.resolve(name1), obj1)
        self.assertEqual(initial_naming_context.resolve(qual_name_1), obj1)
        # Unbind it and verify the object is not present in context and the initial context anymore,
        # and that resolving it fails:
        self.context.unbind(name1)
        self.assertNotIn(name1, self.context)
        self.assertNotIn(qual_name_1, initial_naming_context)
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.resolve(name1)
        self.assertEqual(exc.exception.name, name1)
        self.assertEqual(exc.exception.binding_type, BindingType.named_object)
        with self.assertRaises(NameNotFoundException) as exc:
            initial_naming_context.resolve(qual_name_1)
        self.assertEqual(exc.exception.name, name1)
        self.assertEqual(exc.exception.binding_type, BindingType.named_object)

        # Add binding to subcontext and verify unbinding it one the main context using the composite name:
        qual_name_2 = self.context.bind(name2, obj2)   
        self.assertIn(name2, self.context)
        self.assertIn(qual_name_2, initial_naming_context)
        self.assertEqual(self.context.resolve(name2), obj2)
        self.assertEqual(initial_naming_context.resolve(qual_name_2), obj2)
        # Unbind it and verify the object is not present in context and the initial context anymore,
        # and that resolving it fails:
        self.context.unbind(name2)
        self.assertNotIn(name2, self.context)
        self.assertNotIn(qual_name_2, initial_naming_context)
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.resolve(name2)
        self.assertEqual(exc.exception.name, name2[-1])
        self.assertEqual(exc.exception.binding_type, BindingType.named_object)
        with self.assertRaises(NameNotFoundException) as exc:
            initial_naming_context.resolve(qual_name_2)
        self.assertEqual(exc.exception.name, name2[-1])
        self.assertEqual(exc.exception.binding_type, BindingType.named_object)

    def test_unbind_context(self):
        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.unbind_context(None)
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.unbind_context(invalid_name)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

        # Unbinding should fail when no existing binding was found:
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.unbind_context('subcontext')
        self.assertEqual(exc.exception.name, 'subcontext')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)

        # Bind new context to be able to verify unbinding it:
        subcontext = self.context.bind_new_context('subcontext')
        name, obj = 'obj', object()
        qual_name = subcontext.bind(name, obj)
        self.assertIn(name, subcontext)
        self.assertIn(('subcontext', name), self.context)
        self.assertIn(qual_name, initial_naming_context)
        self.assertEqual(self.context.resolve(('subcontext', name)), obj)
        self.assertEqual(initial_naming_context.resolve(qual_name), obj)
        # Unbind the subcontext it and verify the object is not present in the main context and the initial context anymore,
        # and that resolving it and its bounded objects fails:
        self.context.unbind_context('subcontext')
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.resolve_context('subcontext')
        self.assertEqual(exc.exception.name, 'subcontext')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)
        self.assertNotIn(('subcontext', name), self.context)
        self.assertNotIn(qual_name, initial_naming_context)
        with self.assertRaises(NameNotFoundException) as exc:
            self.context.resolve(('subcontext', name))
        self.assertEqual(exc.exception.name, 'subcontext')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)
        with self.assertRaises(NameNotFoundException) as exc:
            initial_naming_context.resolve(qual_name)
        self.assertEqual(exc.exception.name, 'subcontext')
        self.assertEqual(exc.exception.binding_type, BindingType.named_context)
        # The unbound context should now also throw unbound exceptions:
        with self.assertRaises(UnboundException):
            subcontext.bind('test', object())

    def test_resolve_context(self):
        # Verify general exceptions raised for name-context resolving.
        # Regular behaviour is tested in this case throughout after binding values.

        # In case of a regular NamingContext, assert that the action throws the appropriate UnboundException,
        # and bind the context to the initial context.
        # Actions on the InitialNamingContext, which is bounded by default, should work out of the box.
        if not isinstance(self.context, InitialNamingContext):
            with self.assertRaises(UnboundException):
                self.context.resolve_context('test')
            # Bind the context to the initial context
            initial_naming_context.bind_context(self.context_name, self.context)

        # Verify invalid names throw the appropriate exception:
        for invalid_name in self.invalid_names:
            with self.assertRaises(NamingException) as exc:
                self.context.resolve_context(invalid_name)
            self.assertEqual(exc.exception.message, NamingException.Message.invalid_name)

class AbstractNamingContextCase(unittest.TestCase):

    def setUp(self):
        super().setUp()
        # Store a copy of initial context's bindings before each test,
        # so that they can be reinstated in the tear down afterwards.
        self.initial_context_bindings = {k:copy.copy(v) for k,v in InitialNamingContext()._bindings.items()}
        self.context = self.new_context()

    def tearDown(self):
        super().tearDown()
        # Reinstate initial context's bindings.
        InitialNamingContext()._bindings = self.initial_context_bindings

class NamingContextCase(AbstractNamingContextCase, NamingContextCaseMixin):

    context_name = ('context',)
    context_cls = NamingContext

class InitialNamingContextCase(NamingContextCase):

    context_name = tuple()
    context_cls = InitialNamingContext

    def test_singleton(self):
        # Verify the InitialNamingContext is a singleton.
        self.assertEqual(initial_naming_context, InitialNamingContext())
        self.assertEqual(InitialNamingContext(), InitialNamingContext())
        initial_naming_context.bind('test', object())
        self.assertEqual(initial_naming_context._bindings, InitialNamingContext()._bindings)

class ConstantNamingContextCaseMixin(AbstractNamingContextCaseMixin):

    context_cls = ConstantNamingContext
    constant_type = None

    # Constant naming context only allows string names, but allows the empty string:
    invalid_names = [None, tuple(), ('',), (None,), ('test', ''), ('test', None), ('test',), ('test', 'test')]
    valid_names = ['', 'x', '-1', '0', '1', 'True', '1.5', 'test']

    # Names may be valid arguments, but still fail the resolve (e.g. the conversion to the constant type).
    # So define the compatible and incompatible set to verify in concrete cases.
    incompatible_names = None
    compatible_names = None

    def new_context(self):
        return self.context_cls(self.constant_type)

    def test_resolve(self):
        super().test_resolve()

        for name, expected in self.compatible_names:
            self.assertEqual(self.context.resolve(name), expected)

        for incompatible_name in self.incompatible_names:
            with self.assertRaises(NameNotFoundException) as exc:
                self.context.resolve(incompatible_name)
            self.assertEqual(exc.exception.name, incompatible_name)
            self.assertEqual(exc.exception.binding_type, BindingType.named_object)

class StringNamingContextCase(AbstractNamingContextCase, ConstantNamingContextCaseMixin):

    context_name = ('str',)
    constant_type = str

    incompatible_names = []
    compatible_names = [(name, name) for name in ConstantNamingContextCaseMixin.valid_names]

class IntegerNamingContextCase(AbstractNamingContextCase, ConstantNamingContextCaseMixin):

    context_name = ('int',)
    constant_type = int

    incompatible_names = ['', 'x', 'True', '1.5', 'test']
    compatible_names = [('-1', -1), ('0', 0), ('2', 2)]

class BooleanNamingContextCase(AbstractNamingContextCase, ConstantNamingContextCaseMixin):

    context_name = ('bool',)
    constant_type = bool

    incompatible_names = ['', 'x', '-1', '0', '1', 'True', '1.5', 'test']
    compatible_names = [('True', True), ('False', False), ('2', 2)]
