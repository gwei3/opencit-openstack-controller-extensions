from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
import six

from nova import db
from nova import exception
from nova import objects
from nova.objects import base
from nova.objects import fields

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


@base.NovaObjectRegistry.register
class HVMetadata(base.NovaPersistentObject, base.NovaObject,
                 base.NovaObjectDictCompat):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'id': fields.IntegerField(read_only=True),
        'compute_node_id': fields.IntegerField(),
        'key': fields.StringField(nullable=False),
        'value': fields.StringField(nullable=True)
        }

    @staticmethod
    #Converts the db object into HVMetadata object
    def _from_db_object(context, hvspec, db_hvspec):
        for key in hvspec.fields:
            #retrieve the value from db object
            value = db_hvspec[key]
            #store the same value in HVMetadata object
            hvspec[key] = value

        hvspec._context = context
        hvspec.obj_reset_changes()
        return hvspec

    def obj_load_attr(self, attrname):
        self.id = self.get_by_id(self.id)
        self.obj_reset_changes(['id'])

    @base.remotable
    def create(self):
        if self.obj_attr_is_set('id'):
            raise exception.ObjectActionError(action='create',
                                              reason='already created')
        updates = self.obj_get_changes()
        db_hvspec = db.hvspec_create(self._context, updates)
        self._from_db_object(self._context, self, db_hvspec)

    @base.remotable
    def save(self, prune_stats=False):
        updates = self.obj_get_changes()
        db_hvspec = db.hvspec_update(self._context, self.id, updates)
        self._from_db_object(self._context, self, db_hvspec)

    @base.remotable
    def destroy(self):
        db.hvspec_delete(self._context, self.id)

    @base.remotable_classmethod
    def destroy_by_id(cls, context, hvspec_id):
        db.hvspec_delete(context, hvspec_id)

    @base.remotable_classmethod
    def get_by_id(cls, context, hvspec_id):
        db_hvspec = db.hvspec_get(context, hvspec_id)
        return cls._from_db_object(context, cls(), db_hvspec)

    @base.remotable_classmethod
    def get_by_compute_node_id_and_key(cls, context, compute_node_id, key):
        db_hvspec = db.hvspec_get_by_compute_node_id_and_key(context, compute_node_id, key)
        return cls._from_db_object(context, cls(), db_hvspec)


@base.NovaObjectRegistry.register
class HVMetadataList(base.ObjectListBase, base.NovaObject):
    # Version 1.0: Initial version
    VERSION = '1.0'
    fields = {
        'objects': fields.ListOfObjectsField('HVMetadata'),
        }

    @base.remotable_classmethod
    def get_all(cls, context):
        db_hvspecs = db.hvspec_get_all(context)
        return base.obj_make_list(context, cls(context), objects.HVMetadata,
                                  db_hvspecs)

    @base.remotable_classmethod
    def get_by_compute_node_id(cls, context, compute_node_id):
        try:
            db_hvspecs = db.hvspec_get_by_compute_node_id(context,
                                                           compute_node_id)

        except exception.ComputeHostNotFound(host=compute_node_id):
            db_hvspecs = []
        return base.obj_make_list(context, cls(context), objects.HVMetadata,
                                  db_hvspecs)

    @base.remotable_classmethod
    def get_by_key(cls, context, key):
        try:
            db_hvspecs = db.hvspec_get_by_key(context,
                                               key)

        except exception.HVMetadataNotFound(host=key):
            db_hvspecs = []
        return base.obj_make_list(context, cls(context), objects.HVMetadata,
                                  db_hvspecs)
