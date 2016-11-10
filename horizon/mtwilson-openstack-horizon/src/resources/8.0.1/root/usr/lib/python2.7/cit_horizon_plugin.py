from django.utils.translation import ugettext_lazy as _
from django.template import defaultfilters as filters
from django.conf import settings  # noqa
from horizon import tables
from horizon import forms

from openstack_dashboard.dashboards.admin.hypervisors import tables as hypervisors_tables
from openstack_dashboard.dashboards.admin.hypervisors import tabs as hypervisors_tabs

from openstack_dashboard.dashboards.admin.images import tables as images_tables
from openstack_dashboard.dashboards.admin.images import views as images_view

from openstack_dashboard.dashboards.project.images.images import tables as proj_images_tables
from openstack_dashboard.dashboards.project.images.images import forms as proj_images_forms
from openstack_dashboard.dashboards.project.images import views as proj_images_main_view
from openstack_dashboard.dashboards.project.images.images import views as proj_images_view

from openstack_dashboard.dashboards.admin.instances import tables as instances_tables
from openstack_dashboard.dashboards.admin.instances import views as instances_view
from openstack_dashboard.dashboards.project.instances import tables as project_instances_tables
from openstack_dashboard.dashboards.project.instances import views as project_instances_view

import asset_tag_utils
import logging
import json


LOG = logging.getLogger(__name__)


def safe_from_escaping(value):
    return filters.safe(value)

# BEGIN: Changes to add the Geo Tag column in the Instances table view

def generate_attestation_status_str_for_instance(policy, policy_status, attestation, trustRequired, trustStatus, assetTagRequired, assetTagPresent):

    return_string = "<span class='fa {}' title='{}'></span><span class='fa {}' title='{}'></span><img style='height: 18px; padding-left: 10px;' src='{}' title='{}' />"
    classSpan1=''
    tooltipSpan1=''
    classSpan2=''
    tooltipSpan2=''
    
    if trustRequired == True:
        if attestation == True:
            if trustStatus == True:
                classSpan1 = 'green_lock'
                tooltipSpan1 = 'Trust Required and Trusted Host'
            else:
                classSpan1 = 'red_unlock'
                tooltipSpan1 = 'Trust Required and Untrusted Host'
        else:
            classSpan1 = 'red_unlock'
            tooltipSpan1 = 'Trust Required and No attestation for host'
    else:
        classSpan1 = 'gray_unlock'
        tooltipSpan1 = 'Trust Not Required'

    if assetTagRequired == True:
        if assetTagPresent == True:
            if trustStatus == True:
                classSpan2 = 'green_pin'
                tooltipSpan2 = 'Asset Tag Required and present and Trusted'
            else:
                classSpan2 = 'red_pin'
                tooltipSpan2 = 'Asset Tag Required and present and Not Trusted'
        else:
            classSpan2 = 'red_pin'
            tooltipSpan2 = 'Asset Tag Required and not present'
    else:
         classSpan2 = 'gray_pin'
         tooltipSpan2 = 'Asset Tag Not Required'

    launch_image_name = "/static/dashboard/img/policy_unknown.png"
    launch_image_tooltip = 'Launch policy: Unknown'

    if policy is None:
        launch_image_tooltip = ''
    elif policy == 'MeasureOnly':
        if policy_status == 'true':
            launch_image_name = '/static/dashboard/img/measure_success.png'
            launch_image_tooltip = 'Launch policy: Measured and launched'
        else:
            launch_image_name = '/static/dashboard/img/measure_fail.png'
            launch_image_tooltip = 'Launch policy: Failed VM measure'
    elif policy == 'MeasureAndEnforce':
        if policy_status == 'true':
            launch_image_name = '/static/dashboard/img/measure_enforce_success.png'
            launch_image_tooltip = 'Launch policy: Measured and Enforced'
        else:
            launch_image_name = '/static/dashboard/img/measure_enforce_fail.png'
            launch_image_tooltip = 'Launch policy: Failed VM measure'

    finalStr = return_string.format(classSpan1, tooltipSpan1, classSpan2, tooltipSpan2, launch_image_name, launch_image_tooltip)

    return finalStr

def get_instance_attestation_status(instance):
    attestation = False
    trustStatus = False
    trustRequired = False
    assetTagPresent = False
    assetTagRequired = False

    policy = None
    policy_status = None

    hostname = getattr(instance, 'OS-EXT-SRV-ATTR:host', None)
    LOG.error("hostname: %s" %hostname)

    if hostname is not None:
        instance_metadata = getattr(instance, 'metadata', None)
        LOG.error("instance_metadata %s" %instance_metadata)
        tag_dictionary = getattr(instance, 'tag_properties', None)
        LOG.error("tag_dictionary : %s" %tag_dictionary)
        trustReport = getattr(instance, 'attestation_status', None)
        LOG.error("trustReport : %s" %trustReport)

        if 'measurement_policy' in instance_metadata:
            policy = instance_metadata['measurement_policy']
            policy_status = instance_metadata['measurement_status']

        assetTags = {}
        if trustReport is not None:
            attestation = True
            trustStatus, assetTags = asset_tag_utils.isHostTrusted(trustReport)

        LOG.error("trustStatus : %s assetTags : %s" % (trustStatus, assetTags))
        if tag_dictionary != None and tag_dictionary != '-' and tag_dictionary != 'None':
            if type(tag_dictionary) is unicode:
                tag_dictionary = tag_dictionary.encode('utf8')

            if type(tag_dictionary) is str:
                tag_dictionary = json.loads(tag_dictionary)

            if ('mtwilson_trustpolicy_location' in tag_dictionary and tag_dictionary['mtwilson_trustpolicy_location'] != None) or ('trust' in tag_dictionary and tag_dictionary['trust'] == 'true'):
                trustRequired = True

                if 'tags' in tag_dictionary:
                    tags = tag_dictionary['tags']

                    if tags != None and tags != {} and tags != 'None':
                        assetTagRequired = True

                        assetTagPresent = asset_tag_utils.isAssetTagsPresent(assetTags, tags)
                        LOG.error("assetTagPresent : %s" % assetTagPresent)
 
    return generate_attestation_status_str_for_instance(policy, policy_status, attestation, trustRequired, trustStatus, assetTagRequired, assetTagPresent)

class GeoTagInstancesTable(project_instances_tables.InstancesTable):

    attestation_status = tables.Column(get_instance_attestation_status,
        verbose_name=_("Attestation Status"),
        filters=(safe_from_escaping,))

    class Meta(instances_tables.AdminInstancesTable.Meta):
        name = "instances"
        columns = ('name', 'image_name', 'attestation_status', 'ip', 'size', 'keypair', 'status', 'az', 'task', 'state', 'created')
        verbose_name = _("Instances")
        status_columns = ["status", "task"]
        row_class = project_instances_tables.UpdateRow
        table_actions = (project_instances_tables.LaunchLink, project_instances_tables.SoftRebootInstance, project_instances_tables.DeleteInstance, project_instances_tables.InstancesFilterAction)
        row_actions = (project_instances_tables.StartInstance, project_instances_tables.ConfirmResize, project_instances_tables.RevertResize,
                       project_instances_tables.CreateSnapshot, project_instances_tables.SimpleAssociateIP, project_instances_tables.AssociateIP,
                       project_instances_tables.SimpleDisassociateIP, project_instances_tables.EditInstance,
                       project_instances_tables.DecryptInstancePassword, project_instances_tables.EditInstanceSecurityGroups,
                       project_instances_tables.ConsoleLink, project_instances_tables.LogLink, project_instances_tables.TogglePause, project_instances_tables.ToggleSuspend,
                       project_instances_tables.ResizeLink, project_instances_tables.SoftRebootInstance, project_instances_tables.RebootInstance,
                       project_instances_tables.StopInstance, project_instances_tables.RebuildInstance, project_instances_tables.DeleteInstance)

class GeoTagAdminInstancesTable(instances_tables.AdminInstancesTable):

    attestation_status = tables.Column(get_instance_attestation_status,
        verbose_name=_("Attestation Status"),
        filters=(safe_from_escaping,))

    class Meta(instances_tables.AdminInstancesTable.Meta):
        name = "instances"
        columns = ('host', 'name', 'image_name', 'attestation_status', 'ip', 'size', 'status', 'task', 'state', 'created')

instances_view.AdminIndexView.table_class = GeoTagAdminInstancesTable
project_instances_view.IndexView.table_class = GeoTagInstancesTable

# END: Changes to add the Geo Tag column in the Instances table view

# BEGIN: Changes to add the Geo Tag column in the hypervisors table view

def generate_attestation_status_str_for_host(attestation, trustStatus, assetTagPresent, assetTags):
    return_string = "<span class='fa {}' title='{}'></span><span class='fa {}' title='{}'></span>"
    classSpan1 = ''
    tooltipSpan1 = ''
    classSpan2 = ''
    tooltipSpan2 = '' 

    if attestation == True:
        if trustStatus == True: 
            classSpan1 = 'green_lock'
            tooltipSpan1 = 'Trusted Host'
        else:
            classSpan1 = 'red_unlock'
            tooltipSpan1 = 'Untrusted Host'
    else:
        classSpan1 = 'gray_unlock'
        tooltipSpan1 = 'No Attestaion for host'

    if assetTagPresent == True:
        if trustStatus == True:
            classSpan2 = 'green_pin'
            tooltipSpan2 = json.dumps(assetTags)
        else:
            classSpan2 = 'red_pin'
            tooltipSpan2 = 'Asset Tag present and Not Trusted'
    else:
        classSpan2 = 'gray_pin'
        tooltipSpan2 = 'Asset Tag not present'

    finalStr = return_string.format(classSpan1, tooltipSpan1, classSpan2, tooltipSpan2)

    return finalStr

def get_host_trust_status(hypervisor):
    trustReport = getattr(hypervisor, 'geo_tag', None)

    attestation = False
    trustStatus = False
    assetTagPresent = False

    assetTags = {}
    if trustReport is not None:
        attestation = True
        trustStatus, assetTags = asset_tag_utils.isHostTrusted(trustReport)

    LOG.error("trustStatus : %s assetTags : %s" % (trustStatus, assetTags))
    if assetTags != None and assetTags != {} and assetTags != 'None':
        assetTagPresent = True

    return generate_attestation_status_str_for_host(attestation, trustStatus, assetTagPresent, assetTags)

class GeoTagHypervisorsTable(hypervisors_tables.AdminHypervisorsTable):

    geo_tag = tables.Column(get_host_trust_status,
        verbose_name=_("Geo/Asset Tag"),
        filters=(safe_from_escaping,))

    class Meta(hypervisors_tables.AdminHypervisorsTable.Meta):
        name = "hypervisors"
        columns = ('hostname', 'geo_tag', 'vcpus', 'vcpus_used', 'memory', 'memory_used', 'local', 'local_used', 'running_vms')

hypervisors_tabs.HypervisorTab.table_classes = (GeoTagHypervisorsTable,)

# END: Changes to add the Geo Tag column in the hypervisors table view

# BEGIN: Changes to add the tag creation in the create image form

def get_tags_json():
    return proj_images_view.asset_tags

class GeoTagCreateImageForm(proj_images_forms.CreateImageForm):

    trust_type = forms.MultipleChoiceField(
        label=_('Trust Policy'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[('trust', _('Trust only')),
                 ('trust_loc', _('Trust and Location'))])

    json_field = forms.CharField(
        label=_("Tags"),
        initial=get_tags_json,
        widget=forms.HiddenInput())

    geoTag = forms.CharField(
        label=_("Tags"),
        widget=forms.HiddenInput())

proj_images_view.CreateView.form_class = GeoTagCreateImageForm
images_view.CreateView.form_class = GeoTagCreateImageForm

# END: Changes to add the tag creation in the create image form

# BEGIN: Changes to add the tag creation in the create image form

def get_image_props(image):
    if 'mtwilson_trustpolicy_location' in image.properties:
        image.properties['trust'] = 'true'
    return image.properties

class GeoTagUpdateImageForm(proj_images_forms.UpdateImageForm):

    trust_type = forms.MultipleChoiceField(
        label=_('Trust Policy'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[('trust', _('Trust only')),
                 ('trust_loc', _('Trust and Location'))])

    json_field = forms.CharField(
        label=_("Tags"),
        initial=get_tags_json,
        widget=forms.HiddenInput())

    properties = forms.CharField(
        label=_("Tags"),
        widget=forms.HiddenInput())

    geoTag = forms.CharField(
        label=_("Tags"),
        widget=forms.HiddenInput())

proj_images_view.UpdateView.form_class = GeoTagUpdateImageForm
images_view.UpdateView.form_class = GeoTagUpdateImageForm

# END: Changes to add the tag creation in the create image form

# BEGIN: Changes to add the Geo Tag column in the Images table view

def generate_attestation_status_str_for_image(trustRequired, assetTagRequired):
    return_string = "<span class='fa {}' title='{}'></span><span class='fa {}' title='{}'></span>"
    classSpan1 = ''
    tooltipSpan1 = ''
    classSpan2 = ''
    tooltipSpan2 = '' 

    if trustRequired == True: 
        classSpan1 = 'green_lock'
        tooltipSpan1 = 'Trust required'
    else:
        classSpan1 = 'gray_unlock'
        tooltipSpan1 = 'Trust not required'

    if assetTagRequired == True:
        classSpan2 = 'green_pin'
        tooltipSpan2 = 'Asset Tags required'
    else:
        classSpan2 = 'gray_pin'
        tooltipSpan2 = 'Asset Tags not required'

    finalStr = return_string.format(classSpan1, tooltipSpan1, classSpan2, tooltipSpan2)
    return finalStr

def get_image_selection(image):
    tag_dictionary = get_image_props(image)

    trustRequired = False
    assetTagRequired = False

    if tag_dictionary != None and tag_dictionary != '-' and tag_dictionary != 'None':
        if type(tag_dictionary) is unicode:
            tag_dictionary = tag_dictionary.encode('utf8')

        if type(tag_dictionary) is str:
            tag_dictionary = json.loads(tag_dictionary)

        if 'trust' in tag_dictionary and tag_dictionary['trust'] == 'true':
            trustRequired = True

            if 'tags' in tag_dictionary:
                tags = tag_dictionary['tags']

                if tags != None and tags != {} and tags != 'None':
                    assetTagRequired = True

    return generate_attestation_status_str_for_image(trustRequired, assetTagRequired)

class GeoTagImagesTable(proj_images_tables.ImagesTable):

    image_policy = tables.Column(get_image_selection,
        verbose_name=_("Image policies"),
        filters=(safe_from_escaping,))

    class Meta(images_tables.AdminImagesTable.Meta):
        name = "images"
        columns = ('name', 'image_type', 'image_policy', 'status', 'public', 'protected', 'disk_format')
        row_class = proj_images_tables.UpdateRow
        status_columns = ["status"]
        verbose_name = _("Images")
        table_actions = (proj_images_tables.OwnerFilter, proj_images_tables.CreateImage, proj_images_tables.DeleteImage,)
        row_actions = (proj_images_tables.LaunchImage, proj_images_tables.CreateVolumeFromImage,
                       proj_images_tables.EditImage, proj_images_tables.DeleteImage,)
        pagination_param = "image_marker"

class GeoTagAdminImagesTable(images_tables.AdminImagesTable):

    image_policy = tables.Column(get_image_selection,
        verbose_name=_("Image policies"),
        filters=(safe_from_escaping,))

    class Meta(images_tables.AdminImagesTable.Meta):
        name = "images"
        columns = ('name', 'image_type', 'image_policy', 'status', 'public', 'protected', 'disk_format')

images_view.IndexView.table_class = GeoTagAdminImagesTable
proj_images_main_view.IndexView.table_class = GeoTagImagesTable
