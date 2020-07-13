import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import requests
import urllib3
import time
import json
import io
from urllib.parse import urlparse


def make_rest_call(url=None, postdata=None, request_type=None, tcSessionId=None, headers=None, ConnectionTimeOut=None):
    """
    This function performs a REST API call and uses Session ID for persistent connection

    Parameters:
        urls:  REST URI for the query
        postdata:  This is the data to post
        request_type:   Type of request to initiate (GET, POST)
        tcSessionId: Providing Session prevents authentication
                      for consecutive sessions
        headers: Headers that needs to be attached with the request
        ConnectionTimeOut: Terminates a connection if it takes longer
                            to give a response. (value in seconds)

    Returns:
        rest_data:  This is the data from the REST query
        status_code: exit status of request
        sessionId: Session ID Created during the request so it can be used
                      in upcoming requests
        response_text: entire response received from server
    """
    if request_type == "GET":
        with requests.get(url, cookies=tcSessionId, timeout=ConnectionTimeOut,
                          headers=headers, verify=False) as r:
            rest_data = r.content
            status_code = r.status_code
            if not tcSessionId:
                try:
                    sessionId = r.cookies['TCSESSIONID']
                except:
                    sessionId = None
            else:
                sessionId = tcSessionId['TCSESSIONID']
            response_text = r.text
        r.close()
    elif request_type == "GETS":
        with requests.get(url, cookies=tcSessionId, timeout=ConnectionTimeOut,
                          headers=headers, verify=False, stream=True) as r:
            rest_data = r.content
            status_code = r.status_code
            if not tcSessionId:
                try:
                    sessionId = r.cookies['TCSESSIONID']
                except:
                    sessionId = None
            else:
                sessionId = tcSessionId['TCSESSIONID']
            response_text = io.BytesIO(r.content)
        r.close()
    elif request_type == "POST":
        with requests.post(url,
                           cookies=tcSessionId,
                           timeout=ConnectionTimeOut,
                           headers=headers,
                           verify=False,
                           data=postdata) as r:
            rest_data = r.content
            status_code = r.status_code
            if not tcSessionId:
                try:
                    sessionId = r.cookies['TCSESSIONID']
                except:
                    sessionId = None
            else:
                sessionId = tcSessionId['TCSESSIONID']
            response_text = r.text
        r.close()
    return rest_data, status_code, sessionId, response_text


def _etree_to_dict(etree):
    """
    Convert an elementTree to a dictionary object

    Parameter
        etree     This is the xml elementTree

    Returns
        data_dict  This is the dictionary created from etree
    """
    data_dict = {etree.tag: {} if etree.attrib else None}
    children = list(etree)
    if children:
        child_data_dict = defaultdict(list)
        for child_data in map(_etree_to_dict, children):
            for key, value in child_data.items():
                child_data_dict[key].append(value)
        data_dict = {
            etree.tag: {
                k: v[0] if len(v) == 1 else v
                for k, v in child_data_dict.items()
            }
        }
    if etree.attrib:
        data_dict[etree.tag].update((k, v) for k, v in etree.attrib.items())
    if etree.text:
        text = etree.text.strip()
        if children or etree.attrib:
            if text:
                data_dict[etree.tag]['#text'] = text
        else:
            data_dict[etree.tag] = text
    return data_dict


def initiate_rest_call(url=None, postdata="", datatype="json", tcSessionId=None, ConnectionTimeOut=None,
                       serverUrl=None, requestType=None):
    """
    This function identifies headers and request type, and takes care of data classification

    Parameters:
        urls:  REST URI for the query
        postdata:  This is the data to post
        type:      This is the data type to expect (json, xml, text)
        tcSessionId: Providing Session prevents authentication
                      for consecutive sessions
        ConnectionTimeOut: Terminates a connection if it takes longer
                            to give a response. (value in seconds)

    Returns:
        rest_data:  This is the data from the REST query
        status_code: exit status of request
        sessionId: Session ID Created during the request so it can be used
                      in upcoming requests
        response_text: entire response received from server
    """
    url = url.replace('/httpAuth/', '/')
    if datatype == 'json':
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Origin': serverUrl}
        if requestType == None:
            requestType = "GET"
        rest_data, status_code, sessionId, response_text = make_rest_call(
            url, postdata, requestType, tcSessionId, headers,
            ConnectionTimeOut)
        try:
            rest_data = json.loads(rest_data)
        except:
            rest_data = None
    elif datatype == 'xml':
        headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml', 'Origin': serverUrl}
        if requestType == None:
            requestType = "POST"
        rest_data, status_code, sessionId, response_text = make_rest_call(
            url, postdata, requestType, tcSessionId, headers,
            ConnectionTimeOut)
        try:
            element_tree = ET.XML(rest_data)
            rest_data = _etree_to_dict(element_tree)
        except:
            rest_data = None
    elif datatype == 'text':
        headers = {
            'Content-Type': 'text/plain',
            'Accept': 'text/plain',
            'Origin': serverUrl
        }
        if requestType == None:
            requestType = "GET"
        rest_data, status_code, sessionId, response_text = make_rest_call(
            url, postdata, requestType, tcSessionId, headers,
            ConnectionTimeOut)
        try:
            rest_data = rest_data.decode('utf-8').strip("\n")
        except:
            rest_data = None

    elif datatype == 'zip':
        headers = {
            'Content-Type': 'application/zip',
            'Accept': 'application/octet-stream',
            'Origin': serverUrl
        }
        if requestType == None:
            requestType = "GETS"
        rest_data, status_code, sessionId, response_text = make_rest_call(
            url, postdata, requestType, tcSessionId, headers,
            ConnectionTimeOut)

    return rest_data, status_code, sessionId, response_text


def teamcity_rest_call_reuse_session(server=None, rest_uri=None, user=None, password=None,
                                     postdata="", datatype="json", debugout=False, tcSessionId=None,
                                     ConnectionTimeOut=180, requestType=None, retry_attempt=10,
                                     sleep_seconds=30):
    """
    This function gathers data and generates URL required to initiate a REST API Call
    it uses the provided Session ID, and tried to generate a session using that
    If the sessionID is not provided or it is expired, this function generates a new
    one and returns that sessionID, which should be parsed in future session requests
    Parameters:
        server:             Server address (URL)
        rest_uri:           REST URI for the query
        user:               REST user
        password:           Password to authenticate user
        postdata:           This is the data to post
        type:               This is the data type to expect (json, xml, text)
        tcSessionId:        Providing Session prevents authentication
                            for consecutive sessions
        ConnectionTimeOut:  Terminates a connection if it takes longer
                            to give a response. (value in seconds)
        requestType:        Accepted Values are GET or POST
        retry_attempt:      Retry the same request on certain conditions
        sleep_seconds:      sleep between retires

    Returns:
        rest_data:  This is the data from the REST query
        tcSessionId: Session ID Created during the request so it can be used
                      in upcoming requests
    """
    try:
        postdata = str(postdata.decode("utf-8")).replace('\n', '').replace('\r', '')
    except Exception:
        postdata = postdata
    rest_data = ""
    orig_server = server
    serverHost = urlparse(server)
    server = serverHost.netloc
    rest_url = 'https://{0}:{1}@{2}/{3}'.format(user, password, server, rest_uri)
    rest_url_no_pass = 'https://{0}/{1}'.format(server, rest_uri)
    serverUrl = 'https://{0}'.format(server)

    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if debugout:
            print("REST request: {}".format(rest_url_no_pass))
            print("Server: {0}".format(server))
            print("rest uri: {0}".format(rest_uri))
            print("user: {0}".format(user))
            print("postdata: {0}".format(postdata))
            print("datatype: {0}".format(datatype))
        if tcSessionId:
            cookies = {'TCSESSIONID': tcSessionId}
            rest_data, status_code, tcSessionId, response_text = initiate_rest_call(
                url=rest_url_no_pass,
                postdata=postdata,
                datatype=datatype,
                tcSessionId=cookies,
                ConnectionTimeOut=ConnectionTimeOut,
                serverUrl=serverUrl,
                requestType=requestType)

            # If above request failed because the cookie expired or access limitation of cookies
            # a second attempt will be initiated with username and password

            if status_code == 401 or status_code == 403:
                print("Using User/Pass because Cookies failed with HTTP {0}".format(status_code))
                cookies = None
                rest_data, status_code, tcSessionId, response_text = initiate_rest_call(
                    url=rest_url,
                    postdata=postdata,
                    datatype=datatype,
                    tcSessionId=cookies,
                    ConnectionTimeOut=ConnectionTimeOut,
                    serverUrl=serverUrl,
                    requestType=requestType)
        else:
            cookies = None
            rest_data, status_code, tcSessionId, response_text = initiate_rest_call(
                url=rest_url,
                postdata=postdata,
                datatype=datatype,
                tcSessionId=cookies,
                ConnectionTimeOut=ConnectionTimeOut,
                serverUrl=serverUrl,
                requestType=requestType)

        if status_code in [500, 502, 503, 401]:
            # If rest api call return following error codes, It would use recursion to retry:
            # HTTP 500 - Internal Server Error
            # HTTP 502 - Bad Gateway
            # HTTP 503 - Service Unavailable
            # HTTP 401 - Unauthorized
            retry_attempt -= 1
            print("REST Request Failed with HTTP {0} URL: {1}. Retrying...".format(status_code, rest_url_no_pass))
            if retry_attempt <= 0:
                return False, tcSessionId
            time.sleep(sleep_seconds)
            rest_data, tcSessionId = teamcity_rest_call_reuse_session(
                server=orig_server,
                rest_uri=rest_uri,
                user=user,
                password=password,
                postdata=postdata,
                datatype=datatype,
                debugout=debugout,
                tcSessionId=tcSessionId,
                ConnectionTimeOut=ConnectionTimeOut,
                requestType=requestType,
                retry_attempt=retry_attempt,
                sleep_seconds=sleep_seconds)
        elif status_code != 200:
            print("REST Request Failed with HTTP {0} URL: {1}".format(status_code, rest_url_no_pass))
            return False, False

    except Exception as e:
        print("Error: Could not connect to the Teamcity Server, Please try re-running build again later.")
        print("Exception details: {}".format(e))
        print("rest_url={}".format(rest_url_no_pass))
    return rest_data, tcSessionId


def get_build_details(project_id, teamcity_url, user, password, isrunning=False, debugout=False,
                      tcSessionId=None):
    """
    Get the details of project_id

    Parameters:
        project_id    This is the project to check
        teamcity_url  The teamcity server to examine
        user          The rest user credential
        password      The password for rest user credential
        tcSessionId   reuse existing sessiong for REST API Calls
    Return
        build_details
    """
    if isrunning:
        build_details_rest_uri = "httpAuth/app/rest/builds/id:{}".format(project_id)
    else:
        build_details_rest_uri = "httpAuth/app/rest/buildTypes/id:{}".format(project_id)
    build_details = {}
    try:
        build_details, tcSessionId = teamcity_rest_call_reuse_session(
            teamcity_url,
            build_details_rest_uri,
            user,
            password,
            debugout=debugout,
            tcSessionId=tcSessionId)
    except Exception as this_exception:
        print("!!! WARNING: {}/{} failed".format(teamcity_url, build_details_rest_uri))
        print(this_exception)
    return build_details, tcSessionId


def trigger_build_with_changeID(config_id=None, premerge_changes=None,
                                tc_internal_change_id=None, properties=None,
                                user=None, password=None, teamcity_url=None,
                                debugout=False, tcSessionId=None, comment=None,
                                bump_to_top=False):
    """
    Set up the buildXML data and use that to trigger a teamcity project build

    Parameters
        config_id:              configuration ID of the build to be triggered
        premerge_changes:       branch having this change
        tc_internal_change_id:  teamcity internal change ID referring to base
                                revision
        properties:             dictionary that contains the build properties
                                to pass to the triggered build
        user:                   active directory user credential to trigger a
                                build
        password:               password to authenticate user
        teamcity_url:           teamcity server URL of the triggered build
        debugout:               enable verbosity
        tcSessionId:            Session ID to enable reuse the existing
                                session of TeamCity
        bump_to_top             Push to the top of the queue

    Return
        triggered_build  json data describing the triggered project
    """
    premerge_changes = "" if premerge_changes == "<default>" else premerge_changes
    print("------ trigger_project: config_id={} ------".format(config_id))
    build_id = []
    build_id.append('<build branchName="{}">'.format(premerge_changes))
    build_id.append('  <buildType id="{}"/>'.format(config_id))
    if bump_to_top:
        build_id.append('  <triggeringOptions queueAtTop="true" />')
    if comment:
        build_id.append('  <comment><text>{}</text></comment>'.format(comment))
    if tc_internal_change_id:
        build_id.append('    <lastChanges>')
        build_id.append('    <change id="{}" personal="false" />'
                        .format(tc_internal_change_id))
        build_id.append('    </lastChanges>')
    build_id.append('  <properties>')
    for prop, value in properties.items():
        build_id.append('    <property name="{}" value="{}"/>'
                        .format(prop, value))
    build_id.append('  </properties>')
    build_id.append('</build>')
    build_id_xml = "\n".join(build_id)
    if debugout:
        print("build_id:\n{}".format(build_id_xml))
    triggered_build = ""
    return_value = ""

    # In case the required fields are not present it will retry the request and will move on
    max_retry = 2
    current = 1
    while current <= max_retry:
        triggered_build, tcSessionId = teamcity_rest_call_reuse_session(
            server=teamcity_url,
            rest_uri="httpAuth/app/rest/buildQueue",
            postdata=bytes(build_id_xml, 'utf-8'),
            datatype="xml",
            user=user,
            password=password,
            tcSessionId=tcSessionId)
        if triggered_build:
            return_value = triggered_build
            if 'build' in triggered_build.keys():
                if 'href' in triggered_build['build'].keys():
                    break
                else:
                    print("--- Retry Attempt {} of {} ---"
                          .format(current, max_retry))
                    print("--- Build Link not found, following is the response received ---")
                    if debugout:
                        print(triggered_build['build'])
            else:
                print("--- Retry Attempt {} of {} ---"
                      .format(current, max_retry))
                print("--- No build reponse received ---")
                if debugout:
                    print(triggered_build)
        current += 1
    return return_value, tcSessionId


def trigger_build_with_same_revision(orig_build=None,
                                     verbose=None,
                                     user=None,
                                     password=None,
                                     teamcity_url=None,
                                     tcSessionId=None,
                                     comment=None,
                                     build_props={},
                                     build_type_id=None,
                                     only_if_finished=True,
                                     total_attempts=120,
                                     sleep=30):
    """
    Input:
        orig_build  : original build which needs to re-triggered
        verbose     : Provide verbose output
        user        : Username of teamcity
        password    : Password of teamcity
        teamcity_url: teamcity server url
        tcSessionId : Re-use same existing session
        comment     : Specify comment for teamcity UI
        build_props : Pass params to build
    Return:
        weburl of the build triggered
    """
    if orig_build:
        # Find BuildType ID, Change ID and branch of original build
        if not only_if_finished:
            total_attempts = 1
        current_attempt = 0
        while True:
            output, tcSessionId = get_build_details(user=user,
                                                    password=password,
                                                    teamcity_url=teamcity_url,
                                                    project_id=orig_build,
                                                    isrunning=True,
                                                    debugout=verbose,
                                                    tcSessionId=tcSessionId)
            if output:
                build_type_id = output.get('buildTypeId')
                branch = output.get('branchName')
                state = output.get('state')
                change_ids = [x.get('id') for x in output.get('lastChanges', {}).get('change', [])]
                change_id = max(change_ids) if len(change_ids) > 0 else None
            else:
                print("ERROR: Original build ID is invalid")
                return False, tcSessionId
            current_attempt += 1
            if state == "running" and current_attempt < total_attempts:
                time.sleep(sleep)
            else:
                break
        if only_if_finished and state == "running":
            print("ERROR: Original build still running, after {} attempts. "
                  "Exit without trigger.".format(total_attempts))
            return False, tcSessionId
    elif build_type_id:
        change_id = ""
        branch = ""
    else:
        print("ERROR: Insufficient input")
        return False, tcSessionId
    # trigger_info, tcSessionId = trigger_build_with_changeID(
    #     config_id=build_type_id,
    #     premerge_changes=branch,
    #     tc_internal_change_id=change_id,
    #     properties=build_props,
    #     user=user,
    #     password=password,
    #     teamcity_url=teamcity_url,
    #     debugout=verbose,
    #     tcSessionId=tcSessionId,
    #     comment=comment)
    # print("Build Triggered:{}".format(trigger_info['build']['webUrl']))
    # return trigger_info['build']['webUrl']
    url = "https://teamcity02-or.intel.com/viewLog.html?buildId=11417887&buildTypeId=SsgCiCtrl_TagAndBuild"
    print("Build Triggered:{}".format(url))
    return url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', help='Username', required=True)
    parser.add_argument('-p', '--password', help='Password', required=True)
    parser.add_argument('-o', '--orig_build', help='Original Build ID', default="")
    parser.add_argument('-th', '--teamcity_host', help='Server hosting Teamcity', required=True)
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('-b', '--build_type_id', help='Build Type ID', default="")
    parser.add_argument('-op', '--other_param', help='Other Params in format "key=value;key=value"', default="")
    parser.add_argument('-r', '--rerun', help='Specify if it is a rerun', action='store_true')

    args = parser.parse_args()
    build_props = {}
    if args.orig_build:
        build_props = {
            'origControlBuildServer': args.teamcity_host,
            'origControlBuildId': args.orig_build
        }
    else:
        build_props = {}
    for kv in args.other_param.split(";"):
        key = kv.split("=")[0]
        val = kv.split("=")[1]
        build_props[key] = val

    trigger_build_with_same_revision(orig_build=args.orig_build,
                                     verbose=args.verbose,
                                     user=args.user,
                                     password=args.password,
                                     teamcity_url=args.teamcity_host,
                                     tcSessionId=None,
                                     comment=None,
                                     build_props=build_props,
                                     build_type_id=args.build_type_id)


if __name__ == "__main__":
    main()
