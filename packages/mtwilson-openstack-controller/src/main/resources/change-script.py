from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

meta = MetaData()

def upgrade(migrate_engine):
    meta.bind = migrate_engine

    compute_nodes = Table('compute_nodes', meta, autoload=True)

    hv_specs = Table('hv_specs', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('deleted_at', DateTime),
        Column('deleted', Integer, default=0, nullable=False),
        Column('id', Integer, primary_key=True),
        Column('compute_node_id', Integer, ForeignKey(compute_nodes.c.id), nullable=False),
        Column('key', String(255), nullable=False),
        Column('value', Text),
        UniqueConstraint(
            'compute_node_id', 'key', 'deleted',
            name='uniq_hv_specs0compute_node_id0key0deleted'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    hv_specs.create(checkfirst=True)

def downgrade(migrate_engine):
    meta.bind = migrate_engine
    hv_specs = Table('hv_specs', meta, autoload=True)
    hv_specs.drop(checkfirst=True)
