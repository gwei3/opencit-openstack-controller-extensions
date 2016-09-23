from nova import exception
from nova import context
from nova import utils
from nova import db

from oslo_config import cfg
from oslo_log import log as logging

import jwt
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend


LOG = logging.getLogger(__name__)

trusted_opts = [
    cfg.StrOpt('signature_verification',
              default='on',
              help='signature verification flag for host trustreport'),
    cfg.StrOpt('signature_algorithm',
              default='RS256',
              help='signature algorithm for host trustreport'),
    cfg.StrOpt('attestation_hub_public_key',
              default='',
              help='attestation hub public key'),
]

CONF = cfg.CONF
trust_group = cfg.OptGroup(name='trusted_computing', title='Trust parameters')
CONF.register_group(trust_group)
CONF.register_opts(trusted_opts, group=trust_group)


class HostTrustUtils():

    def __init__(self):
        self.verification = CONF.trusted_computing.signature_verification
        self.algorithm = CONF.trusted_computing.signature_algorithm
        self.key = CONF.trusted_computing.attestation_hub_public_key
        self.admin = context.get_admin_context()


    def verifySignature(self, signed_trust_report):
        try:
            LOG.info("key : %s" % self.key)
            LOG.info("algorithm : %s" % self.algorithm)
            public_key = utils.execute('cat', self.key, run_as_root=True, check_exit_code=[0])[0]
            trust_report = jwt.decode(signed_trust_report, public_key, self.algorithm)
            return trust_report

        except IOError as exc:
            LOG.exception("Unable to open public key file : %s" % exc)
            raise exc
        except Exception as exc:
            LOG.exception("Signed trust report is being tampered : %s" % exc)
            raise exc


    def getTrustReport(self, compute_node_id):
        trust_report = {}
        try:
            if self.verification == 'on':
                hvspec = db.hvspec_get_by_compute_node_id_and_key(self.admin, compute_node_id, "signed_trust_report")
                signed_trust_report = hvspec['value']

                trust_report = self.verifySignature(signed_trust_report)

            else:
                hvspec = db.hvspec_get_by_compute_node_id_and_key(self.admin, compute_node_id, "trust_report")
                trust_report = hvspec['value']

        except exception.HVMetadataNotFound:
                LOG.exception("Trust Report not found for compute node : %s" % compute_node_id)
        except:
                LOG.exception("Signature Verification failed for compute node : %s" % compute_node_id)
        return trust_report
