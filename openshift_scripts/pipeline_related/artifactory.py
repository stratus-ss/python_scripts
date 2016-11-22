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
    @staticmethod
    def get_latest_version(environment_name, dictionary_with_versions):
        """Get the latest version of a template for a given an environment"""
        latest_version_dict = {}
        for component_name, environment_version in dictionary_with_versions.items():
            for environment in environment_version:
                # put all blueprint versions in a dictionary if then environment name is found in the blueprint name
                # it is expected that blueprint version will be formatted tec-prd_2.0.2 (env_version.number)
                if environment_name == str(environment.split("_")[0]):
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
    def find_artifactory_metadata(cls, property_to_search_for):
        search_results = cls.search_artifactory_api(property_to_search_for)
        component_version_dict = {}
        for uri in search_results['results']:
            component_name_from_uri = uri['uri'].split("/")[-1]
            print(component_name_from_uri)
            for versions in requests.get(uri['uri']).json()['children']:
                common.append_to_single_dimension_dict(component_version_dict, component_name_from_uri, versions['uri'].strip("/"))
        return(component_version_dict)

    @classmethod
    def update_artifactory_metadata(cls, property_to_search_for, values_to_update_dict, append=False):
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
            update_with_this_value = values_to_update_dict[component_name_from_uri]
            update_component(component_name_from_uri, update_with_this_value)

