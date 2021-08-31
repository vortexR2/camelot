# -*- coding: utf-8 -*-
"""
Tests for the Admin classes
"""
import datetime
from decimal import Decimal
from typing import Optional
import unittest
from dataclasses import field, InitVar

from sqlalchemy import orm, schema, sql, types
from sqlalchemy.dialects import mysql
from sqlalchemy.ext import hybrid
from sqlalchemy.orm.session import Session

from .test_model import ExampleModelMixinCase
from .test_orm import TestMetaData
from camelot.admin.application_admin import ApplicationAdmin
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.dataclass_admin import DataclassAdmin
from camelot.admin.field_admin import FieldAdmin
from camelot.admin.not_editable_admin import not_editable_admin
from camelot.admin.object_admin import ObjectAdmin
from camelot.core.dataclasses import dataclass
from camelot.core.sql import metadata
from camelot.model.i18n import Translation
from camelot.model.party import Person, Address
from camelot.view.controls import delegates
from camelot.types.typing import Note, Directory, File


class ApplicationAdminCase(unittest.TestCase):

    def test_application_admin(self):
        app_admin = ApplicationAdmin()
        self.assertTrue( app_admin.get_navigation_menu() )
        self.assertTrue( app_admin.get_related_toolbar_actions( 'onetomany' ) )
        self.assertTrue( app_admin.get_related_toolbar_actions( 'manytomany' ) )
        self.assertTrue( app_admin.get_version() )
        self.assertTrue( app_admin.get_icon() )
        self.assertTrue( app_admin.get_splashscreen() )
        self.assertTrue( app_admin.get_organization_name() )
        self.assertTrue( app_admin.get_organization_domain() )
        self.assertTrue( app_admin.get_stylesheet() )
        self.assertTrue( app_admin.get_about() )
        with self.assertRaises(Exception):
            app_admin.get_related_admin(1)
        self.assertEqual(type(app_admin.get_related_admin(object)), ObjectAdmin)

    def test_admin_for_exising_database( self ):
        from .snippet.existing_database import app_admin
        self.assertTrue(app_admin.get_navigation_menu())

class ObjectAdminCase(unittest.TestCase, ExampleModelMixinCase):
    """Test the ObjectAdmin
    """

    @classmethod
    def setUpClass(cls):
        cls.setup_sample_model()
    
    @classmethod
    def tearDownClass(cls):
        cls.tear_down_sample_model()    

    def setUp(self):
        super( ObjectAdminCase, self ).setUp()
        self.app_admin = ApplicationAdmin()

    def test_not_editable_admin_class_decorator( self ):
        OriginalAdmin = Translation.Admin
        original_admin = OriginalAdmin(self.app_admin, Translation)
        self.assertTrue(len(original_admin.get_list_actions()))
        self.assertTrue(original_admin.get_field_attributes('value')['editable'])
        original_related_admin = original_admin.get_related_admin(Person)

        #
        # enable the actions
        #
        NewAdmin = not_editable_admin(Translation.Admin, actions = True)
        new_admin = NewAdmin(self.app_admin, Translation)
        self.assertTrue(len( new_admin.get_list_actions()))
        self.assertFalse(new_admin.get_field_attributes('value')['editable'])
        self.assertFalse(new_admin.get_field_attributes('source')['editable'])
        new_related_admin = new_admin.get_related_admin(Person)
        self.assertNotEqual(original_related_admin, new_related_admin)

        #
        # make sure the routes are different
        #
        self.assertNotEqual(new_admin.get_admin_route(), original_admin.get_admin_route())
        self.assertEqual(ObjectAdmin.admin_for(new_admin.get_admin_route()), new_admin)
        self.assertEqual(ObjectAdmin.admin_for(original_admin.get_admin_route()), original_admin)
        self.assertNotEqual(new_related_admin.get_admin_route(), original_related_admin.get_admin_route())

        #
        # disable the actions
        #
        NewAdmin = not_editable_admin( Translation.Admin, 
                                       actions = False )
        new_admin = NewAdmin( self.app_admin, Translation )
        self.assertFalse( len( new_admin.get_list_actions() ) )
        self.assertFalse( new_admin.get_field_attributes( 'value' )['editable'] )
        self.assertFalse( new_admin.get_field_attributes( 'source' )['editable'] )

        #
        # keep the value field editable
        #
        NewAdmin = not_editable_admin( Translation.Admin, 
                                       editable_fields = ['value'] )
        new_admin = NewAdmin( self.app_admin, Translation )
        self.assertFalse( len( new_admin.get_list_actions() ) )
        self.assertTrue( new_admin.get_field_attributes( 'value' )['editable'] )
        self.assertFalse( new_admin.get_field_attributes( 'source' )['editable'] )

    def test_signature( self ):
        #
        # Test a group of methods, required for an ObjectAdmin
        #

        class A( object ):

            def __init__( self ):
                self.x = 1
                self.y = 2

            class Admin( ObjectAdmin ):
                verbose_name = u'objèct'
                list_display = ['x', 'y']

        a = A()
        a_admin = self.app_admin.get_related_admin( A )
        self.assertTrue( str( a_admin ) )
        self.assertTrue( repr( a_admin ) )
        self.assertFalse( a_admin.primary_key( a ) )
        self.assertTrue( isinstance( a_admin.get_modifications( a ),
                                     dict ) )
        a_admin.get_icon()
        a_admin.flush( a )
        a_admin.delete( a )
        a_admin.expunge( a )
        a_admin.refresh( a )
        a_admin.add( a )
        a_admin.is_deleted( a )
        a_admin.is_persistent( a )
        a_admin.copy( a )
        self.assertEqual(a_admin.get_verbose_name_plural(), u'objècts')

    def test_property( self ):

        class A(object):

            def __init__(self):
                self.x = 1

            @property
            def y(self):
                return self.x

            @y.setter
            def y(self, value):
                self.x = value

        # test if a default admin is created
        admin = self.app_admin.get_related_admin(A)
        self.assertEqual(type(admin), ObjectAdmin)
        self.assertEqual(admin.entity, A)
        fa = admin.get_field_attributes('y')
        self.assertEqual(fa['editable'], True)

        table = admin.get_table()
        fields = table.get_fields()
        self.assertEqual(fields, ['y'])

        class B(A):

            @property
            def z(self):
                return self.x

            class Admin(ObjectAdmin):
                list_display = ['x', 'y']

        admin = self.app_admin.get_related_admin(B)
        self.assertEqual(type(admin), B.Admin)
        self.assertEqual(admin.entity, B)

        # make sure properties are in the list of fields, even if they don't appear
        # on a list
        fields = admin.get_all_fields_and_attributes()
        self.assertTrue('z' in fields)

        fa = admin.get_field_attributes('y')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['action_routes'], [])
        fa = admin.get_field_attributes('z')
        self.assertEqual(fa['editable'], False)

        table = admin.get_table()
        fields = table.get_fields()
        self.assertEqual(fields, ['x', 'y'])


    def test_typed_property(self):
        
        class TypedPropertyClass(object):
    
            def __init__(self):
                self._test_int = 1
                self._test_bool = False
                self._test_date = datetime.date.today()
                self._test_float = 0.5
                self._test_decimal = 0.75
                self._test_str = 'string'
                self._test_note = 'note'
                self._test_dir = None
                self._test_file = None
                self._test_entity = None
    
            @property
            def test_int(self) -> int:
                return self._test_int
    
            @test_int.setter
            def test_int(self, value):
                self._test_int = value 
                
            @property
            def test_bool(self) -> bool:
                return self._test_bool
        
            @test_bool.setter
            def test_bool(self, value):
                self._test_bool = value
                
            @property
            def test_date(self) -> datetime.date:
                return self._test_date
        
            @test_date.setter
            def test_date(self, value):
                self._test_date = value   
                
            @property
            def test_float(self) -> Optional[float]:
                return self._test_float
        
            @test_float.setter
            def test_float(self, value):
                self._test_float = value 
                
            @property
            def test_decimal(self) -> Decimal:
                return self._test_decimal
        
            @test_decimal.setter
            def test_decimal(self, value):
                self._test_decimal = value 
                
            @property
            def test_str(self) -> str:
                return self._test_str
        
            @test_str.setter
            def test_str(self, value):
                self._test_str = value 
                
            @property
            def test_note(self) -> Note:
                return self._test_note
                
            @property
            def test_dir(self) -> Optional[Directory]:
                return self._test_dir
        
            @test_dir.setter
            def test_dir(self, value):
                self._test_dir = value
                
            @property
            def test_file(self) -> File:
                return self._test_file
        
            @test_file.setter
            def test_file(self, value):
                self._test_file = value 
            
            @property
            def test_entity(self) -> Address:
                return self._test_entity
        
            @test_entity.setter
            def test_entity(self, value):
                self._test_entity = value  
                
            class Admin(ObjectAdmin):
                
                def get_session(self, obj):
                    return Session()
                
        admin = self.app_admin.get_related_admin(TypedPropertyClass)
        self.assertEqual(admin.entity, TypedPropertyClass)
        
        fa = admin.get_field_attributes('test_int')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.IntegerDelegate)
        
        fa = admin.get_field_attributes('test_bool')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.BoolDelegate)  
        
        fa = admin.get_field_attributes('test_date')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.DateDelegate)  
        
        fa = admin.get_field_attributes('test_float')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], True)
        self.assertEqual(fa['delegate'], delegates.FloatDelegate)  
        
        fa = admin.get_field_attributes('test_decimal')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.FloatDelegate) 
        self.assertEqual(fa['decimal'], True,)  
        
        fa = admin.get_field_attributes('test_str')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.PlainTextDelegate)  
        
        fa = admin.get_field_attributes('test_note')
        self.assertEqual(fa['editable'], False)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.NoteDelegate)  
        
        fa = admin.get_field_attributes('test_dir')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], True)
        self.assertEqual(fa['delegate'], delegates.LocalFileDelegate)  
        self.assertEqual(fa['directory'], True,)  
        
        fa = admin.get_field_attributes('test_file')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.LocalFileDelegate)  
        
        fa = admin.get_field_attributes('test_entity')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.Many2OneDelegate) 
        self.assertEqual(fa['target'], Address)
        
        completions = admin.get_completions(TypedPropertyClass(), 'test_entity', '')
        self.assertEqual(completions, [e for e in Session().query(Address).limit(20).all()])
               

    def test_set_defaults(self):

        class A(object):

            def __init__(self):
                self.x = None
                self.y = None
                self.z = None

            class Admin(ObjectAdmin):
                list_display = ['x', 'y', 'z']
                field_attributes = {
                    'z': {'default': 1},
                    'y': {'default': lambda:1},
                    'x': {'default': lambda a:(a.z + a.y) if (a.z and a.y) else None},
                }

        admin = self.app_admin.get_related_admin(A)
        a = A()
        changed = admin.set_defaults(a)
        self.assertEqual(a.z, 1)
        self.assertEqual(a.y, 1)
        self.assertEqual(a.x, 2)
        self.assertEqual(changed, True)
        changed = admin.set_defaults(a)
        self.assertEqual(changed, False)


class DataclassAdminCase(unittest.TestCase, ExampleModelMixinCase):
    """Test the DataclassAdmin
    """

    @classmethod
    def setUpClass(cls):
        cls.setup_sample_model()
    
    @classmethod
    def tearDownClass(cls):
        cls.tear_down_sample_model()    

    def setUp(self):
        super( DataclassAdminCase, self ).setUp()
        self.app_admin = ApplicationAdmin()

    def test_dataclassfields(self):
        
        @dataclass
        class TestDataClass(object):
    
            test_int: Optional[int] = field(default = 1, init = False)
            test_bool: bool = field(default = False, init = False)
            test_date: datetime.date = field(default_factory = datetime.date.today, init = False)
            test_float: float = field(default = 0.5, init = False)
            test_decimal: Decimal = field(default = 0.75, init = False)
            test_str: str = field(default = 'string', init = False)
            test_note: Optional[Note] = field(default = 'note', init =False)
            test_dir: Directory = field(default = None, init = False)
            test_file: Optional[File] = field(default = None, init = False)
            test_entity: Address = field(default = None, init = False)
            test_initvar: InitVar[int] = None
            
            def __post_init__(self, test_initvar):
                self.test_int = test_initvar
    
            @property
            def test_prop(self) -> int:
                return self._test_prop
                
            class Admin(DataclassAdmin):
                
                def get_session(self, obj):
                    return Session()
                
        admin = self.app_admin.get_related_admin(TestDataClass)
        self.assertEqual(admin.entity, TestDataClass)
        
        fa = admin.get_field_attributes('test_int')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], True)
        self.assertEqual(fa['delegate'], delegates.IntegerDelegate)
        
        fa = admin.get_field_attributes('test_bool')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.BoolDelegate)  
        
        fa = admin.get_field_attributes('test_date')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.DateDelegate)  
        
        fa = admin.get_field_attributes('test_float')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.FloatDelegate)  
        
        fa = admin.get_field_attributes('test_decimal')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.FloatDelegate) 
        self.assertEqual(fa['decimal'], True,)  
        
        fa = admin.get_field_attributes('test_str')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.PlainTextDelegate)  
        
        fa = admin.get_field_attributes('test_note')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], True)
        self.assertEqual(fa['delegate'], delegates.NoteDelegate)  
        
        fa = admin.get_field_attributes('test_dir')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.LocalFileDelegate)  
        self.assertEqual(fa['directory'], True,)  
        
        fa = admin.get_field_attributes('test_file')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], True)
        self.assertEqual(fa['delegate'], delegates.LocalFileDelegate)  
        
        fa = admin.get_field_attributes('test_entity')
        self.assertEqual(fa['editable'], True)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.Many2OneDelegate) 
        self.assertEqual(fa['target'], Address)
        
        completions = admin.get_completions(TestDataClass(), 'test_entity', '')
        self.assertEqual(completions, [e for e in Session().query(Address).limit(20).all()])
        
        fa = admin.get_field_attributes('test_prop')
        self.assertEqual(fa['editable'], False)
        self.assertEqual(fa['nullable'], False)
        self.assertEqual(fa['delegate'], delegates.IntegerDelegate) 
        
        fa = admin.get_field_attributes('test_initvar')
        self.assertEqual(fa['editable'], False)
        self.assertEqual(fa['nullable'], True)
        self.assertEqual(fa['delegate'], delegates.PlainTextDelegate)  
        
        test1 = TestDataClass()
        self.assertEqual(test1.test_int, None)
        test2 = TestDataClass(test_initvar = 10)
        self.assertEqual(test2.test_int, 10)
        
    def dataclass_validation(self):
        class TestClass(object):
            
            class Admin(DataclassAdmin):
                pass
            
        test = TestClass
                           
class EntityAdminCase(TestMetaData):
    """Test the EntityAdmin
    """

    def setUp( self ):
        super( EntityAdminCase, self ).setUp()
        self.app_admin = ApplicationAdmin()

    def test_sql_field_attributes( self ):
        #
        # test a generic SQLA field type
        #
        column_1 =  schema.Column( types.Unicode(), nullable = False )
        fa_1 = EntityAdmin.get_sql_field_attributes( [column_1] )
        self.assertTrue( fa_1['editable'] )
        self.assertFalse( fa_1['nullable'] )
        self.assertEqual( fa_1['delegate'], delegates.PlainTextDelegate )
        #
        # test sql standard types
        #
        column_2 =  schema.Column( types.FLOAT(), nullable = True )
        fa_2 = EntityAdmin.get_sql_field_attributes( [column_2] )
        self.assertTrue( fa_2['editable'] )
        self.assertTrue( fa_2['nullable'] )
        self.assertEqual( fa_2['delegate'], delegates.FloatDelegate )
        #
        # test a vendor specific field type
        #
        column_3 = schema.Column( mysql.BIGINT(), default = 2 )
        fa_3 = EntityAdmin.get_sql_field_attributes( [column_3] )
        self.assertTrue( fa_3['default'] )
        self.assertEqual( fa_3['delegate'], delegates.IntegerDelegate )

    def test_field_admin( self ):

        class A(self.Entity):
            a = schema.Column( types.Integer(), FieldAdmin(editable=False,
                                                           maximum=10) )

            class Admin(EntityAdmin):
                pass

        self.create_all()
        admin = self.app_admin.get_related_admin( A )

        fa = admin.get_field_attributes('a')
        self.assertEqual( fa['editable'], False )
        self.assertEqual( fa['maximum'], 10 )

    def test_hybrid_properties( self ):

        class A(self.Entity):

            a = schema.Column(types.Unicode(10))

            @hybrid.hybrid_property
            def h(self):
                return self.a

            @h.setter
            def h(self, value):
                self.a = value

            @h.expression
            def h(cls):
                return sql.select([cls.a]).where(cls.id==A.id)

            @hybrid.hybrid_property
            def i(self):
                return self.a

            @i.expression
            def i(cls):
                return cls.a

            class Admin(EntityAdmin):
                pass

        self.create_all()
        admin = self.app_admin.get_related_admin(A)
        fa = admin.get_field_attributes('h')
        self.assertEqual( fa['editable'], True )
        self.assertTrue( fa['operators'] )
        self.assertEqual( fa['field_name'], 'h' )
        
        fa = admin.get_field_attributes('i')
        self.assertEqual( fa['editable'], False )
        self.assertEqual( fa['field_name'], 'i' )

    def test_relational_field_attributes( self ):

        class A(self.Entity):

            class Admin(EntityAdmin):
                list_display = ['b', 'd', 'related_a']
                field_attributes = {'b':{'column_width': 61},
                                    'd':{'column_width': 73}}

        class B(self.Entity):

            class Admin(EntityAdmin):
                pass

        class C(self.Entity):
            pass

        class D(self.Entity):
            pass

        class E(self.Entity):
            pass

        A.b_id = schema.Column(types.Integer(), schema.ForeignKey(B.id))
        A.b = orm.relationship(B, backref='a')
        A.related_a_id = schema.Column(types.Integer(), schema.ForeignKey(A.id))
        A.related_a = orm.relationship(A, backref=orm.backref('a', remote_side=[A.id]))
        t = schema.Table('table', metadata, schema.Column('a_id', types.Integer(), schema.ForeignKey(A.id)),
                         schema.Column('e_id', types.Integer(), schema.ForeignKey(E.id)))
        A.e = orm.relationship(E, secondary=t, foreign_keys=[t.c.a_id, t.c.e_id])
        C.a_id = schema.Column(types.Integer(), schema.ForeignKey(A.id))
        C.a = orm.relationship(A, backref=orm.backref('c', uselist=False))
        D.a_id = schema.Column(types.Integer(), schema.ForeignKey(A.id))
        D.a = orm.relationship(A, backref=orm.backref('d', lazy='dynamic'))


        self.create_all()
        a_admin = self.app_admin.get_related_admin( A )

        b_fa = a_admin.get_field_attributes('b')
        self.assertEqual( b_fa['delegate'], delegates.Many2OneDelegate )
        self.assertTrue(len(b_fa['actions']))

        c_fa = a_admin.get_field_attributes('c')
        self.assertEqual( c_fa['delegate'], delegates.Many2OneDelegate )

        d_fa = a_admin.get_field_attributes('d')
        self.assertEqual( d_fa['delegate'], delegates.One2ManyDelegate )
        self.assertTrue(len(d_fa['actions']))

        e_fa = a_admin.get_field_attributes('e')
        self.assertEqual( e_fa['delegate'], delegates.One2ManyDelegate )
        self.assertTrue(len(e_fa['actions']))

        b_admin = self.app_admin.get_related_admin( B )
        a_fa = b_admin.get_field_attributes('a')
        self.assertEqual( a_fa['column_width'], 2*(61+73))

    def test_custom_relation_admin(self):
        from .snippet.admin_field_attribute import (MailingGroup,
                                                    PersonOnMailingGroupAdmin)
        admin = self.app_admin.get_related_admin(MailingGroup)
        persons_fa = admin.get_field_attributes('persons')
        self.assertTrue(isinstance(persons_fa['admin'], PersonOnMailingGroupAdmin))

    def test_entity_validation(self):

        class A(self.Entity):
            pass

        class B(self.Entity):
            a_id = schema.Column(types.Integer(), schema.ForeignKey(A.id), nullable=False)
            a = orm.relationship(A)
            x = schema.Column(types.Integer(), nullable=False)
            z = schema.Column(types.Integer())

            class Admin(EntityAdmin):
                list_display = ['a', 'x', 'z']
                field_attributes = {
                    'z': {'nullable': False}
                }

        self.create_all()
        admin = self.app_admin.get_related_admin(B)
        validator = admin.get_validator()
        b = B()
        # new object has 3 not nullable fields
        self.assertEqual(len(validator.validate_object(b)), 3)
        # complete the fields required in the database
        b.a = A()
        b.x = 3
        self.assertEqual(len(validator.validate_object(b)), 1)
        self.session.flush()
        # once flushed the object is valid, this ensures that objects
        # loaded from the db are always valid
        self.assertEqual(len(validator.validate_object(b)), 0)
        # once the object is changed, they are validated again
        b.x = 4
        self.assertEqual(len(validator.validate_object(b)), 1)
        # completing all fields makes it valid
        b.z = 14
        self.assertEqual(len(validator.validate_object(b)), 0)
