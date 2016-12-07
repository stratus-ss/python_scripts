#!/usr/bin/env python
import json
import re
import requests
import urlparse
import os
import argparse
import tempfile
import traceback
import sys
import common, log


class ArtifactoryApi():
    def __init__(self):
        self.local_dir = tempfile.mkdtemp()
        self.dml_host = common.get_dml()
        self.dml_repositories = common.get_dml_repositories()
        self.SOURCE_DML = "https://repository.rnd.amadeus.net"

    def __del__(self):
        '''
            Automatically delete downloaded artifacts when class instance is destroyed
        '''
        import shutil
        shutil.rmtree(self.local_dir)

    @staticmethod
    def get_latest_version(environment_name, dictionary_with_versions, major_version_to_check_for):
        """Get the latest version of a template for a given an environment"""
        latest_version_dict = {}
        for component_name, environment_version in dictionary_with_versions.items():
            for environment in environment_version:
                # put all blueprint versions in a dictionary if then environment name is found in the blueprint name
                # it is expected that blueprint version will be formatted tec-prd_2.0.2 (env_version.number)
                if environment_name == str(environment.split("_")[0]):
                    # The major version should always come after the underscore and be the first 2 digits which
                    # are separated by a decimal point
                    major_version_in_list = environment.split('_')[1].split(".")[0] + '.' + \
                                            environment.split('_')[1].split(".")[1]
                    # The reason to deconstruct and then reconstruct the environmnet name is that it is posible to
                    # have multiple minor revisions such as 1.1.4.22.3 in which case you cannot cheat and just remove
                    # the trailing decimal point
                    major_version_with_comp_in_list = component_name + "_" + major_version_in_list
                    if major_version_with_comp_in_list in major_version_to_check_for:
                        # associate a component with a specific blueprint
                        common.append_to_single_dimension_dict(latest_version_dict, component_name, environment)
        # Go through the dictionary and redefine each component with the latest blueprint version
        for key in latest_version_dict.keys():
            latest_version = max(latest_version_dict[key])
            latest_version_dict[key] = latest_version
        return(latest_version_dict)

    @staticmethod
    def search_artifactory_api(property_to_search_for):
        search_url = "http://repository.rnd.amadeus.net/repository/api/search/prop?%s" % property_to_search_for
        # This returns a json doc that looks like {"results": {"uri": "http://someurl"}}
        search_results = requests.get(search_url).json()
        return search_results

    @classmethod
    def return_all_objects_underneath_folder_with_specific_metadata(cls, property_to_search_for):
        search_results = cls.search_artifactory_api(property_to_search_for)
        component_version_dict = {}
        for uri in search_results['results']:
            component_name_from_uri = uri['uri'].split("/")[-1]
            log.debug("Processing %s with the uri: %s" % (component_name_from_uri, uri['uri']))
            for versions in requests.get(uri['uri']).json()['children']:
                common.append_to_single_dimension_dict(component_version_dict, component_name_from_uri,
                                                       versions['uri'].strip("/"))
        return(component_version_dict)

    @classmethod
    def update_artifactory_metadata(cls, property_to_search_for, values_to_update_dict, disable_artifactory_tagging,
                                    append=False):
        """
        updates the metadata on an object in artifactory.
        """
        def update_component(component_to_update, updated_value):
            updated_value_converted_to_string = ",".join(updated_value)
            property_json = requests.get(property_uri).json()
            # current_property_value returns a list
            current_property_value = property_json['properties']['%s' % property_to_search_for]
            if append:
                # Turn the list into a string, otherwise artifactory posts values like [u"[u'1.0"',u"'7779']", '79']
                new_value = ",".join(current_property_value) + "," + updated_value_converted_to_string
            else:
                new_value = updated_value_converted_to_string
            # put the major version tag unless told otherwise
            if not disable_artifactory_tagging:
                put_property_uri = property_uri + "=%s=%s&recursive=0" % (property_to_search_for, new_value)
                log.debug("Updating the following URL: \t%s" % put_property_uri)
                log.debug("Http status code of put: %s" % requests.put(put_property_uri).status_code)
        search_results = cls.search_artifactory_api(property_to_search_for)

        for uri in search_results['results']:
            property_uri = uri['uri'] + "?properties"
            # scrape the component name out of the URI to make sure that the component you want to update
            # is exactly the component in the URI (to avoid updating adminui-sso when you meant to update adminui only
            if "environment" in uri['uri']:
                component_name_from_uri = uri['uri'].split("/")[-2]
            elif "component" in uri['uri']:
                component_name_from_uri = uri['uri'].split("/")[-1]
            else:
                log.error("Unable to get component from expected URL")
                sys.exit(1)
            try:
                update_with_this_value = values_to_update_dict[component_name_from_uri]
                update_component(component_name_from_uri, update_with_this_value)
            except KeyError:
                log.warning("Unable to find the following component in the conf file you passed in >>>> %s <<<<"
                            % component_name_from_uri)

    def retrieve_blueprints(self, cmp_name, cmp_version, env_version):
        '''
            Download all blueprints for the specified acs component
            Blueprints will be downloaded once locally then reused when needed

            local_dir
            |--cmp_name
            |  |--component
            |  |  |--cmp_version
            |  |  |  |--config.json
            |  |  |  |--cmp_name-cmp_version.json
            |  |  |  |--DeploymentConfig
            |  |  |  |  |--openshift_object_name
            |  |  |  |  |   |--config.json
            |  |  |  |  |   |--object.json
            |  |  |  |  |   |--registrator.json
            |  |  |  |--Service
            |  |  |  |  |--service_object_name
            |  |  |  |  |   |--object.json
            |  |  |  |--Endpoints
            |  |  |  |  |--endpoint_object_name
            |  |  |  |  |   |--object.json
            |  |--environment
            |  |  |-- env_version
            |  |  |  |--config.json
            |  |  |  |-- cmp_name-env_version.json
    '''
        missing_blueprints = []
        invalid_json_blueprints = []

        ############################
        # get component blueprint
        try:
            (component_blueprints_path, blueprint_repo, cmp_blueprint_json) = \
                self.__retrieve_acs_blueprint(cmp_name, cmp_version, 'component')

            ############################
            # get openshift object blueprints
            for openshift_object in cmp_blueprint_json['content']:
                object_name = openshift_object.get('name')
                base_url = openshift_object['object']

                sub_object_response = self.__get_sub_blueprint(base_url, blueprint_repo)
                if sub_object_response.status_code != requests.codes.ok:
                    missing_blueprints.append("Missing openshift object blueprint '%s'" % base_url)
                    continue

                try:
                    # escape place holder used for environment blueprint to get a valid json
                    sub_object = sub_object_response.text
                    regex = re.compile(r'\${[\w0-9]*}')  # ${VARIABLE}
                    sub_object_modified = re.sub(regex, "0", sub_object)
                    sub_object_json = json.loads(sub_object_modified)
                except ValueError:
                    invalid_json_blueprints.append("Openshift object blueprint is not a valid json '%s'" % base_url)
                    continue

                object_blueprint_path = os.path.join(component_blueprints_path,
                                                     sub_object_json['kind'],
                                                     sub_object_json['metadata']['name'])

                if not os.path.exists(object_blueprint_path):
                    os.makedirs(object_blueprint_path)
                with open(os.path.join(object_blueprint_path, 'object.json'), 'w') as sub_object_file:
                    sub_object_file.write(sub_object)

                if object_name:
                    # set local path of object at component level
                    objects_references = self.get_config_value(cmp_name, cmp_version, 'component', 'objects_references')
                    if not objects_references:
                        objects_references = {}
                    objects_references[object_name] = os.path.join(object_blueprint_path, 'object.json')
                    self.set_config_value(cmp_name, cmp_version, 'component', 'objects_references', objects_references)

                    # set object_name name from component blueprint at object level
                    self.set_config_value(cmp_name, cmp_version, 'component', 'object_name',
                                          object_name, sub_object_json['kind'], sub_object_json['metadata']['name'])

                if sub_object_json['kind'] == 'DeploymentConfig':
                    pod_name = sub_object_json['metadata']['name']
                    ############################
                    # get registrator blueprint
                    registrator_config = None
                    for container in sub_object_json['spec']['template']['spec']['containers']:
                        if container['name'] == 'registrator' or container['image'].startswith('acs/registrator'):
                            for arg in container['args']:
                                if arg.startswith('--config-'):
                                    registrator_config_path = arg.split("=")[-1]
                                    resgitrator_config_response = self.__get_sub_blueprint(registrator_config_path, blueprint_repo)
                                    if resgitrator_config_response.status_code != requests.codes.ok:
                                        missing_blueprints.append("Missing registrator config '%s'" % registrator_config_path)

                                    # check blueprint is a valid json
                                    try:
                                        registrator_config = resgitrator_config_response.json()
                                    except ValueError:
                                        invalid_json_blueprints.append("Invalid json syntax for registrator config '%s'" %
                                                                       (registrator_config_path))
                                    break
                            # we found a registrator container but no config associated
                            if not registrator_config:
                                missing_blueprints.append("Missing config file for pod '%s' and container '%s'" % (pod_name, container['name']))
                            break

                    if registrator_config:
                        registrator_config_path = os.path.join(object_blueprint_path, 'registrator.json')
                        with open(registrator_config_path, 'w') as registrator_config_file:
                            registrator_config_file.write(resgitrator_config_response.text)
        except FileAlreadyExistsException:
            pass  # nothing to do, blueprint already retrieved

        # get environment blueprint
        if env_version:
            try:
                self.__retrieve_acs_blueprint(cmp_name, env_version, 'environment')
            except FileAlreadyExistsException:
                pass  # nothing to do, blueprint already retrieved

        # check for errors
        if len(missing_blueprints) > 0:
            raise FileNotFoundException("Following blueprints not found (dml repositories: %s):\n%s"
                                         % (','.join(self.dml_repositories), json.dumps(missing_blueprints, indent=4)))

        if len(invalid_json_blueprints) > 0:
            raise InvalidJsonSyntaxException("Following blueprints contain invalid json (dml repositories: %s):\n%s"
                                             % (','.join(self.dml_repositories), json.dumps(invalid_json_blueprints, indent=4)))

    def get_acs_blueprint_path(self, cmp_name, version, dml_repo, blueprint_type, dml_host=None):
        '''
            get full path in artifactory for specified blueprint
        '''
        sub_folder = None
        if blueprint_type == 'component':
            sub_folder = 'components'
        elif blueprint_type == 'environment':
            sub_folder = 'environments'
        else:
            log.error("Invalid blueprint type '%s'" % blueprint_type)

        return "%s/%s/%s/%s/%s/%s-%s.json" % (dml_host or self.dml_host, dml_repo, sub_folder, cmp_name, version, cmp_name, version)

    def print_tree(self, sub_path=None, print_files=False):
        '''
            Display directory structure of the retrieved artifacts
        '''
        lookup_path = self.local_dir
        if sub_path:
            lookup_path = os.path.join(lookup_path, sub_path)
        cmd = "find '%s'" % lookup_path
        files = os.popen(cmd).read().strip().split('\n')
        padding = '|  '
        for filepath in files:
            level = filepath.count(os.sep)
            pieces = filepath.split(os.sep)
            symbol = {0:'', 1:'/'}[os.path.isdir(filepath)]
            if not print_files and symbol != '/':
                continue
            print padding * level + pieces[-1] + symbol

    def __get_config_path(self, cmp_name, version, bp_type, object_type=None, object_name=None):
        '''
            get path of the config.json file in directory structure
        '''
        cmp_config_path = os.path.join(self.local_dir, cmp_name, bp_type, version)
        if object_type:
            cmp_config_path = os.path.join(cmp_config_path, object_type)
        if object_name:
            cmp_config_path = os.path.join(cmp_config_path, object_name)
        return os.path.join(cmp_config_path, 'config.json')

    def get_config_value(self, cmp_name, version, bp_type, key, object_type=None, object_name=None):
        '''
            retrieve property value for the specified artifact
        '''
        cmp_config_path = self.__get_config_path(cmp_name, version, bp_type, object_type, object_name)
        if os.path.exists(cmp_config_path):
            with open(cmp_config_path) as cmp_config_file:
                file_content = cmp_config_file.read()
                file_content_json = json.loads(file_content)
                return file_content_json.get(key)

    def set_config_value(self, cmp_name, version, bp_type, key, value, object_type=None, object_name=None):
        '''
            set property value for the specified artifact
        '''
        cmp_config_path = self.__get_config_path(cmp_name, version, bp_type, object_type, object_name)
        if not os.path.exists(cmp_config_path):
            if not os.path.exists(os.path.dirname(cmp_config_path)):
                os.makedirs(os.path.dirname(cmp_config_path))
            with open(cmp_config_path, 'w') as cmp_config_file:
                cmp_config_file.write(json.dumps({key:value}))
        else:
            with open(cmp_config_path, 'r+') as cmp_config_file:
                file_content_json = json.loads(cmp_config_file.read())
                file_content_json[key] = value
                cmp_config_file.seek(0)
                cmp_config_file.write(json.dumps(file_content_json))
                cmp_config_file.truncate()

    def force_blueprint_replication(self, cmp_name, cmp_version, blueprint_type='component'):
        '''
            when not using SOURCE_DML, will force replication of acs blueprint from SOURCE_DML to the current dml
        '''
        # nothing to do if target and source are the same
        if urlparse.urlparse(self.dml_host).hostname == urlparse.urlparse(self.SOURCE_DML).hostname:
            return

        try:
            # check if blueprint is missing targeted dml
            for dml_repo in self.dml_repositories:
                path = self.get_acs_blueprint_path(cmp_name, cmp_version, dml_repo, blueprint_type)
                response = requests.head(path)
                if response.status_code == requests.codes.ok:
                    # we force replication only if artifact is not found
                    return

            for dml_repo in self.dml_repositories:
                path = self.get_acs_blueprint_path(cmp_name, cmp_version, dml_repo, blueprint_type, self.SOURCE_DML)
                response = requests.get(path)
                if response.status_code == requests.codes.ok:
                    # artifact found in SOURCE_DML for this repo
                    break
        except:
            log.info(traceback.format_exc())

    def get_acs_blueprint(self, cmp_name, bp_version, bp_type='component'):
        '''
            retrieve local acs blueprint content as json object

            @param bp_type: possible values : ['component', 'environment']
        '''
        cmp_dir = os.path.join(self.local_dir, cmp_name, bp_type, bp_version)
        cmp_blueprint_path = os.path.join(cmp_dir, '%s-%s.json' % (cmp_name, bp_version))
        with open(cmp_blueprint_path) as cmp_blueprint_file:
            return json.loads(cmp_blueprint_file.read())

    def get_openshift_blueprint(self, cmp_name, cmp_version, object_type=None, object_name=None, dict_result=False):
        '''
            retrieve local openshift blueprint(s) content as :
                - json object if specific object_name requested
                - else : list of json objects

            @param bp_type: possible values : ['component', 'environment']
        '''
        lookup_dir = os.path.join(self.local_dir, cmp_name, 'component', cmp_version)
        if not os.path.exists(lookup_dir):
            self.retrieve_blueprints(cmp_name, cmp_version, None)

        if object_type:
            lookup_dir = os.path.join(lookup_dir, object_type)
            if object_name:
                lookup_dir = os.path.join(lookup_dir, object_name)
        result = []
        escape_var_regex = re.compile(r'\${[\w0-9]*}')  # ${VARIABLE}
        for root, _, files in os.walk(lookup_dir):
            if 'object.json' in files:
                with open(os.path.join(root, 'object.json'), "r") as obj_blueprint_file:
                    # escape place holder used for environment blueprint to get a valid json
                    sub_object_modified = re.sub(escape_var_regex, "0", obj_blueprint_file.read())
                    result.append(json.loads(sub_object_modified))
        return result

    def __retrieve_acs_blueprint(self, cmp_name, bp_version, bp_type='component'):
        '''
            Download acs blueprint from artifactory
        '''
        # get component blueprint
        blueprints_path = os.path.join(self.local_dir, cmp_name, bp_type, bp_version)
        if os.path.exists(blueprints_path):
            raise FileAlreadyExistsException(blueprints_path)

        blueprint_content = None
        blueprint_repo = None
        blueprint_path = None
        for dml_repo in self.dml_repositories:
            blueprint_path = self.get_acs_blueprint_path(cmp_name, bp_version, dml_repo, bp_type)
            response = requests.get(blueprint_path)
            if response.status_code == requests.codes.ok:
                blueprint_content = response.text
                blueprint_repo = dml_repo
                break

        if not blueprint_content:
            raise FileNotFoundException("No %s blueprint for '%s:%s' in dml '%s' for the following repositories : '%s'" %
                                        (bp_type, cmp_name, bp_version, self.dml_host, ','.join(self.dml_repositories)))
        else:
            try:
                blueprint_json = json.loads(blueprint_content)
            except ValueError:
                raise InvalidJsonSyntaxException("Component blueprint is not a valid json '%s'" % blueprint_path)

            if not os.path.exists(blueprints_path):
                os.makedirs(blueprints_path)
            blueprint_path = os.path.join(blueprints_path, '%s-%s.json' % (cmp_name, bp_version))
            with open(blueprint_path, 'w') as blueprint_file:
                blueprint_file.write(blueprint_content)

        return (blueprints_path, blueprint_repo, blueprint_json)

    def __get_sub_blueprint(self, base_url, blueprint_repo):
        '''
            download openshift object blueprint from url found in component blueprint
        '''
        blueprint_url = base_url
        if blueprint_url.startswith('http'):
            blueprint_response = requests.get(blueprint_url)
        else:
            # build url with dml + base_url from component blueprint
            blueprint_url = urlparse.urljoin(self.dml_host, base_url)
            blueprint_response = requests.get(blueprint_url)
            if blueprint_response.status_code == 404:
                # build url with dml + repo +  base_url from component blueprint
                blueprint_url = urlparse.urljoin(self.dml_host, blueprint_repo + '/' + base_url)
                blueprint_response = requests.get(blueprint_url)

        return blueprint_response

    def get_acs_object_name(self, cmp_name, cmp_version, object_type, openshift_object_name):
        '''
            retrieve name of openshift object in acs component blueprint from real name of openshift object
            (they are 2 distinct names that could be different
        '''
        return self.get_config_value(cmp_name, cmp_version, 'component', 'object_name', object_type, openshift_object_name)

    def get_object_blueprint_from_acs_object_name(self, cmp_name, cmp_version, object_name, json_format=True):
        '''
            retrieve openshift object blueprint from name from acs blueprint
        '''
        objects_references = self.get_config_value(cmp_name, cmp_version, 'component', 'objects_references')
        if objects_references:
            blueprint_path = objects_references.get(object_name)
            if blueprint_path:
                with open(blueprint_path) as sub_object_file:
                    sub_object_content = sub_object_file.read()
                    if json_format:
                        # escape place holder used for environment blueprint to get a valid json
                        regex = re.compile(r'\${[\w0-9]*}')  # ${VARIABLE}
                        sub_object_modified = re.sub(regex, "0", sub_object_content)
                        return json.loads(sub_object_modified)
                    else:
                        return sub_object_content

    def get_registrator_config(self, cmp_name, cmp_version, object_name=None):
        '''
            Get json list of registrator configs for the specified component
        '''
        lookup_dir = os.path.join(self.local_dir,
                                  cmp_name,
                                  'component',
                                  cmp_version,
                                  'DeploymentConfig')

        if not os.path.exists(lookup_dir):
            self.retrieve_blueprints(cmp_name, cmp_version, None)

        if object_name:
            lookup_dir = os.path.join(lookup_dir, object_name)

        result = []
        for root, _, files in os.walk(lookup_dir):
            if 'registrator.json' in files:
                with open(os.path.join(root, 'registrator.json')) as registrator_config_file:
                    result.append(json.loads(registrator_config_file.read()))

        return result


class ArtifactException(Exception):
    pass


class FileAlreadyExistsException(ArtifactException):
    pass


class FileNotFoundException(ArtifactException):
    pass


class InvalidJsonSyntaxException(ArtifactException):
    pass


if __name__ == "__main__":
    main_parser = argparse.ArgumentParser(description='Test module')

    main_parser.add_argument('-f', '--env-file', required=True, help='File defining environment variables related to '
                                                                     'current user')
    main_parser.add_argument('-c', '--component', required=True, help='Component and version to check '
                                                                      '(format cmp_name:cmp_version)')

    options = main_parser.parse_args()

    os.environ['ENV_FILE'] = options.env_file
    log.info("Using config from '%s' file" % common.get_env_file())
    common.validate_user_env_file()

    artifactoryApi = ArtifactoryApi()

    artifactoryApi.retrieve_blueprints(options.component.split(':')[0],
                                       options.component.split(':')[1],
                                       None)
    artifactoryApi.print_tree(print_files=True)
