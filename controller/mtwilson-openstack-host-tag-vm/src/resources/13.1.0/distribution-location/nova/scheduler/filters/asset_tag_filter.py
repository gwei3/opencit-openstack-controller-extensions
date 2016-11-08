# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 Intel, Inc.
# Copyright (c) 2011-2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Filter to add support for Trusted Computing Pools.

Filter that only schedules tasks on a host if the integrity (trust)
of that host matches the trust requested in the `extra_specs' for the
flavor.  The `extra_specs' will contain a key/value pair where the
key is `trust'.  The value of this pair (`trusted'/`untrusted') must
match the integrity of that host (obtained from the Attestation
service) before the task can be scheduled on that host.

Note that the parameters to control access to the Attestation Service
are in the `nova.conf' file in a separate `trust' section.  For example,
the config file will look something like:

    [DEFAULT]
    verbose=True
    ...
    [trust]
    server=attester.mynetwork.com

Details on the specific parameters can be found in the file `trust_attest.py'.

Details on setting up and using an Attestation Service can be found at
the Open Attestation project at:

    https://github.com/OpenAttestation/OpenAttestation
"""

from nova import db
from nova import context
from oslo_log import log as logging
from nova.scheduler import filters
from nova.openstack.common import asset_tag_utils
from nova.openstack.common import host_trust_utils


LOG = logging.getLogger(__name__)


class TrustAssertionFilter(filters.BaseHostFilter):

    def __init__(self):
        self.utils = host_trust_utils.HostTrustUtils()
        self.compute_nodes = {}
        self.admin = context.get_admin_context()

        # Fetch compute node list to initialize the compute_nodes,
        # so that we don't need poll OAT service one by one for each
        # host in the first round that scheduler invokes us.
        self.compute_nodes = db.compute_node_get_all(self.admin)


    def host_passes(self, host_state, spec_obj):
        """Only return hosts with required Trust level."""

		verify_asset_tag = False
        verify_trust_status = False

        #spec = filter_properties.get('request_spec', {})
        image_props = spec_obj.image.properties

        trust_verify = image_props.get('trust')
        if('mtwilson_trustpolicy_location' in image_props):
            LOG.info(image_props.get('mtwilson_trustpolicy_location'))
            trust_verify = 'true'

        LOG.debug("trust_verify : %s" % trust_verify)

        #if tag_selections is None or tag_selections == 'Trust':
		if trust_verify == 'true':
            verify_trust_status = True
            # Get the Tag verification flag from the image properties
            tag_selections = image_props.get('tags') # comma separated values
            LOG.debug("tag_selections : %s" % tag_selections)
            if tag_selections != None and tag_selections != {} and  tag_selections != 'None':
                verify_asset_tag = True

        LOG.debug("verify_trust_status : %s" % verify_trust_status)
        LOG.debug("verify_asset_tag : %s" % verify_asset_tag)

        if not verify_trust_status:
            # Filter returns success/true if neither trust or tag has to be verified.
            return True

        #Fetch compute node record for this hypervisor
        compute_node = db.compute_node_search_by_hypervisor(self.admin, host_state.hypervisor_hostname)
        compute_node_id = compute_node[0]['id']
        LOG.debug("compute_node_is : %s" % compute_node_id)

        trust_report = self.utils.getTrustReport(compute_node_id)
        LOG.debug("trust_report : %s" % trust_report)

        if trust_report is None:
            #No attestation found for this host
            return False

        trust, asset_tag = asset_tag_utils.isHostTrusted(trust_report)
        LOG.debug("trust : %s" % trust)
        LOG.debug("asset_tag : %s" % asset_tag)
        if not trust:
            return False

        if verify_asset_tag:
            # Verify the asset tag restriction
            return asset_tag_utils.isAssetTagsPresent(asset_tag, tag_selections)


        return True
