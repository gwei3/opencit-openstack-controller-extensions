# Copyright (c) 2012 OpenStack Foundation
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

"""The hypervisors admin extension."""
from oslo_log import log as logging
import webob.exc

from nova.api.openstack import common
from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova import compute
from nova import exception
from nova.i18n import _
from nova import servicegroup

import json
from collections import defaultdict
from nova.openstack.common import host_trust_utils


LOG = logging.getLogger(__name__)
ALIAS = "os-hypervisors"
authorize = extensions.os_compute_authorizer(ALIAS)


class HypervisorsController(wsgi.Controller):
    """The Hypervisors API controller for the OpenStack API."""

    def __init__(self):
        self.api = compute.HVMetadataAPI()
        self.host_api = compute.HostAPI()
        self.servicegroup_api = servicegroup.API()
        super(HypervisorsController, self).__init__()

    #clean the hv_metadata object for showing to user
    def _filter_hvspec(self, hvspec, **attrs):
        clean = {
            'id': hvspec.id,
            'compute_node_id': hvspec.compute_node_id,
            'key': hvspec.key,
            'value': hvspec.value,
            }
        for attr in attrs:
            clean[attr] = hvspec[attr]
        return clean

    #search compute node corresponding to given hostname or hostip
    def _search_compute_node(self, context, hostname):
        compute_node = self.host_api.compute_node_search_by_hypervisor(context, hostname)
        LOG.debug("compute_node search by hypervisor : %s" % compute_node)

        if not compute_node:
            compute_node = self.host_api.compute_node_search_by_hostip(context, hostname)
            LOG.debug("compute_node search by hostip : %s" % compute_node)

        return compute_node

    def _view_hypervisor(self, hypervisor, service, detail, servers=None,
                         **kwargs):
        alive = self.servicegroup_api.service_is_up(service)
        hyp_dict = {
            'id': hypervisor.id,
            'hypervisor_hostname': hypervisor.hypervisor_hostname,
            'state': 'up' if alive else 'down',
            'status': ('disabled' if service.disabled
                       else 'enabled'),
            }

        if detail and not servers:
            for field in ('vcpus', 'memory_mb', 'local_gb', 'vcpus_used',
                          'memory_mb_used', 'local_gb_used',
                          'hypervisor_type', 'hypervisor_version',
                          'free_ram_mb', 'free_disk_gb', 'current_workload',
                          'running_vms', 'cpu_info', 'disk_available_least',
                          'host_ip'):
                hyp_dict[field] = hypervisor[field]

            hyp_dict['service'] = {
                'id': service.id,
                'host': hypervisor.host,
                'disabled_reason': service.disabled_reason,
                }

        if servers:
            hyp_dict['servers'] = [dict(name=serv['name'], uuid=serv['uuid'])
                                   for serv in servers]

        # Add any additional info
        if kwargs:
            hyp_dict.update(kwargs)

        return hyp_dict

    @extensions.expected_errors((400, 403, 409))
    #@validation.schema(hvspecs.create)
    def create(self, req, body, **hvspec_filters):
        """Create hypervisor metadata."""
        context = req.environ['nova.context']
        authorize(context)
        params = body['hostDetailsList']

        hvspecs = []
        for param in params:
            hostname = param['hostname']

            compute_node = self._search_compute_node(context, hostname)
            if not compute_node:
                LOG.info("No Compute Record found for host : %s" % hostname)
                continue

            compute_node_id = compute_node[0]['id']
            LOG.info("compute_node_id : %s" % compute_node_id)

            existing_hvspecs = self.api.get_hv_specs_by_compute_node_id(context, compute_node_id)
            LOG.info("existing_hvspecs : %s" % existing_hvspecs)

            existing_keys = [x['key'] for x in existing_hvspecs]
            existing_ids = [x['id'] for x in existing_hvspecs]

            for k,v in param.iteritems():

                try:
                    if not k in existing_keys:
                        hvspec = self.api.create_hv_spec(
                            context, compute_node_id, k, v)
                    else:
                        idx = existing_keys.index(k)
                        hvspec = self.api.update_hv_spec(
                            context, existing_ids[idx], compute_node_id, k, v)

                except exception.HVMetadataExists as exc:
                    raise webob.exc.HTTPConflict(explanation=exc.format_message())

                hvspec = self._filter_hvspec(hvspec,
                                             **hvspec_filters)
                LOG.info("hvspec : %s" % hvspec)
                hvspecs.append(hvspec)

        LOG.info("hvspecs : %s" % hvspecs)
        return {'hvMetadataList': hvspecs}


    @extensions.expected_errors(404)
    def hvspecs(self, req, **hvspec_filters):
        """List of hypervisors metadata for a user."""
        context = req.environ['nova.context']
        authorize(context)

        hv_specs = self.api.get_hv_specs(context)
        rval = []
        for hv_spec in hv_specs:
            rval.append(self._filter_hvspec(hv_spec,
                                            **hvspec_filters))

        return {'hv_metadata_list': rval}

    @extensions.expected_errors(404)
    def metadata(self, req, id):
        """Returns the trust status of compute node."""
        context = req.environ['nova.context']
        authorize(context)

        hv_specs = self.api.get_hv_specs_by_compute_node_id(context, id)
        result = defaultdict(list)
        result['id'] = id

        for hvspec in hv_specs:
            key = hvspec['key']
            if key == "trust_report":
                utils = host_trust_utils.HostTrustUtils()
                value = utils.getTrustReport(id)
            elif key == "signed_trust_report":
                value = ""
            else:
                value = hvspec['value']
            result[key] = value

        return {'hv_metadata': result}

    @extensions.expected_errors(404)
    def asset_tags(self, req):
        """Returns the asset tags available in db."""
        context = req.environ['nova.context']
        authorize(context)

        hv_specs = self.api.get_hv_specs_by_key(context, "trust_report")
        result = defaultdict(list)

        asset_tags = []
        for hvspec in hv_specs:
            jsonObj = json.loads(hvspec['value'])
            LOG.info("jsonObj : %s" % jsonObj)
            tags = jsonObj['asset_tags']
            LOG.info("tags : %s" % tags)
            for k,v in tags.iteritems():
                for value in v:
                    LOG.info("name : %s, value : %s" % (k, value))
                    asset_tags.append({"name" : k, "value" : value})

        #pushing only the unique asset tag entries
        unique_tags = list(map(dict, frozenset(frozenset(i.items()) for i in asset_tags)))
        result['kv_attributes'] = unique_tags

        return {'asset_tags': result}

    @extensions.expected_errors(404)
    def truststatus(self, req, id):
        """Returns the trust status of compute node."""
        context = req.environ['nova.context']
        authorize(context)

        try:
            utils = host_trust_utils.HostTrustUtils()
            trust_report = utils.getTrustReport(id)
        except (Exception, exception.ComputeHostNotFound):
            msg = _("Trust Report for compute node with ID '%s' could not be found.") % id
            raise webob.exc.HTTPNotFound(explanation=msg)
        
        return {'trust_report': json.loads(trust_report)}

    @extensions.expected_errors(404)
    def delete(self, req, id):
        """Delete hypervisor metadata with a given hostname."""
        context = req.environ['nova.context']
        authorize(context)

        try:
            self.api.delete_hv_spec(context, id)
        except exception.HVMetadataNotFound as exc:
            raise webob.exc.HTTPNotFound(explanation=exc.format_message())

    @extensions.expected_errors(())
    def index(self, req):
        context = req.environ['nova.context']
        authorize(context)
        compute_nodes = self.host_api.compute_node_get_all(context)
        req.cache_db_compute_nodes(compute_nodes)
        return dict(hypervisors=[self._view_hypervisor(
                                 hyp,
                                 self.host_api.service_get_by_compute_host(
                                     context, hyp.host),
                                 False)
                                 for hyp in compute_nodes])

    @extensions.expected_errors(())
    def detail(self, req):
        context = req.environ['nova.context']
        authorize(context)
        compute_nodes = self.host_api.compute_node_get_all(context)
        req.cache_db_compute_nodes(compute_nodes)
        return dict(hypervisors=[self._view_hypervisor(
                                 hyp,
                                 self.host_api.service_get_by_compute_host(
                                     context, hyp.host),
                                 True)
                                 for hyp in compute_nodes])

    @extensions.expected_errors(404)
    def show(self, req, id):
        context = req.environ['nova.context']
        authorize(context)
        try:
            hyp = self.host_api.compute_node_get(context, id)
            req.cache_db_compute_node(hyp)
        except (ValueError, exception.ComputeHostNotFound):
            msg = _("Hypervisor with ID '%s' could not be found.") % id
            raise webob.exc.HTTPNotFound(explanation=msg)
        service = self.host_api.service_get_by_compute_host(
            context, hyp.host)
        return dict(hypervisor=self._view_hypervisor(hyp, service, True))

    @extensions.expected_errors((404, 501))
    def uptime(self, req, id):
        context = req.environ['nova.context']
        authorize(context)
        try:
            hyp = self.host_api.compute_node_get(context, id)
            req.cache_db_compute_node(hyp)
        except (ValueError, exception.ComputeHostNotFound):
            msg = _("Hypervisor with ID '%s' could not be found.") % id
            raise webob.exc.HTTPNotFound(explanation=msg)

        # Get the uptime
        try:
            host = hyp.host
            uptime = self.host_api.get_host_uptime(context, host)
        except NotImplementedError:
            common.raise_feature_not_supported()

        service = self.host_api.service_get_by_compute_host(context, host)
        return dict(hypervisor=self._view_hypervisor(hyp, service, False,
                                                     uptime=uptime))

    @extensions.expected_errors(404)
    def search(self, req, id):
        context = req.environ['nova.context']
        authorize(context)
        hypervisors = self.host_api.compute_node_search_by_hypervisor(
                context, id)
        if hypervisors:
            return dict(hypervisors=[self._view_hypervisor(
                                     hyp,
                                     self.host_api.service_get_by_compute_host(
                                         context, hyp.host),
                                     False)
                                     for hyp in hypervisors])
        else:
            msg = _("No hypervisor matching '%s' could be found.") % id
            raise webob.exc.HTTPNotFound(explanation=msg)

    @extensions.expected_errors(404)
    def servers(self, req, id):
        context = req.environ['nova.context']
        authorize(context)
        compute_nodes = self.host_api.compute_node_search_by_hypervisor(
                context, id)
        if not compute_nodes:
            msg = _("No hypervisor matching '%s' could be found.") % id
            raise webob.exc.HTTPNotFound(explanation=msg)
        hypervisors = []
        for compute_node in compute_nodes:
            instances = self.host_api.instance_get_all_by_host(context,
                    compute_node.host)
            service = self.host_api.service_get_by_compute_host(
                context, compute_node.host)
            hyp = self._view_hypervisor(compute_node, service, False,
                                        instances)
            hypervisors.append(hyp)
        return dict(hypervisors=hypervisors)

    @extensions.expected_errors(())
    def statistics(self, req):
        context = req.environ['nova.context']
        authorize(context)
        stats = self.host_api.compute_node_statistics(context)
        return dict(hypervisor_statistics=stats)


class Hypervisors(extensions.V21APIExtensionBase):
    """Admin-only hypervisor administration."""

    name = "Hypervisors"
    alias = ALIAS
    version = 1

    def get_resources(self):
        resources = [extensions.ResourceExtension(ALIAS,
                HypervisorsController(),
                member_name='os-hypervisor',
                collection_actions={'detail': 'GET',
                                    'statistics': 'GET',
                                    'hvspecs':'GET',
                                    'asset_tags':'GET'},
                member_actions={'uptime': 'GET',
                                'search': 'GET',
                                'servers': 'GET',
                                'truststatus': 'GET',
                                'metadata': 'GET'})]

        return resources

    def get_controller_extensions(self):
        return []
