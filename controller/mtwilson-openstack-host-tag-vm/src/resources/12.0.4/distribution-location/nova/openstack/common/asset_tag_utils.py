import datetime
import logging
import json
import ast


LOG = logging.getLogger(__name__)


def isHostTrusted(trust_report):
    trust = False
    assetTags = {}

    jsonObj = json.loads(trust_report)

    if 'trusted' in jsonObj:
        if jsonObj['trusted'] == True:
            validTo = jsonObj['valid_to']
            currentUtcTime = datetime.datetime.utcnow()

            #formatting the validTo time to match currentUtcTime format
            vDate = validTo[0:10]
            vTime = validTo[11:19]
            validToFormatted = vDate + " " + vTime
            validTime = datetime.datetime.strptime(validToFormatted, "%Y-%m-%d %H:%M:%S")

            maxTime = max(currentUtcTime, validTime)
            if maxTime == validTime:
                trust = True

    if 'asset_tags' in jsonObj:
        assetTags = jsonObj['asset_tags']

    return trust, assetTags


# Verifies the asset tag match with the tag selections provided by the user.
def isAssetTagsPresent(host_tags, tag_selections):
    # host_tags is the list of tags set on the host
    # tag_selections is the list of tags set as the policy of the image
    ret_status = False

    try:
        sel_tags = ast.literal_eval(tag_selections)

        LOG.info("host_tags : %s" % host_tags)
        LOG.info("sel_tags : %s" % sel_tags)
        iteration_status = True
        for tag in list(sel_tags.keys()):
            LOG.info("tag : %s, host_tags[tag] : %s, sel_tags[tags] : %s" % (tag, host_tags[tag], sel_tags[tag]))
            #checking each value of sel_tags list in host_tags list
            if tag not in list(host_tags.keys()) or not all(item in host_tags[tag] for item in sel_tags[tag]):
                iteration_status = False
        if iteration_status:
            ret_status = True
    except:
        LOG.exception("Exception in ast.literal_eval")
        ret_status = False

    return ret_status
