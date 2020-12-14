#!/usr/bin/env python3

# Copyright 2020 Kohl's Department Stores, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import tempfile
import os
import yaml
import subprocess

# appendResourceVersion - patches the YAML&JSON files in $MANIFEST_DIR,
# adding the metadata.resourceVersion for each resource being managed.
# This is intended to serve as a locking mechanism when applying resources
# in which Kubernetes will fail the apply with a StatusConflict (HTTP status code 409)
# Ref https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md#concurrency-control-and-consistency

# Inputs:
#
# MANIFEST_DIR env var

if __name__ == "__main__":
    manifest_dir = os.getenv('MANIFEST_DIR')
    with open('/var/run/secrets/kubernetes.io/serviceaccount/token') as x: token = x.read()
    for filename in os.listdir(manifest_dir):
        if filename.endswith(".yml") or filename.endswith(".yaml") or filename.endswith(".json"):
            try:
                data = yaml.safe_load(subprocess.run(["kubectl",
                    "-s",
                    "https://kubernetes.default.svc:443",
                    "--token",
                    token,
                    "--certificate-authority",
                    "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
                    "get",
                    "--ignore-not-found",
                    "-f",
                    os.path.join(manifest_dir, filename),
                    "-o",
                    "yaml"], stdout=subprocess.PIPE).stdout)
                #data = yaml.safe_load(subprocess.run(["kubectl",
                #    "get",
                #    "--ignore-not-found",
                #    "-f",
                #    os.path.join(manifest_dir, filename),
                #    "-o",
                #    "yaml"], stdout=subprocess.PIPE).stdout)
                if data is None:
                    print("No kubectl get output for file: {}".format(os.path.join(manifest_dir, filename)))
                    continue
                if "kind" in data and data["kind"] == "List":
                    print("It's a List")
                    if "items" not in data:
                        print("Zero items in k8s List")
                        continue
                    resource_version = {}
                    for item in data["items"]:
                        if "metadata" in item and "resourceVersion" in item["metadata"]:
                            gvk_name = item["apiVersion"] + item["kind"] + item["metadata"]["name"]
                            resource_version[gvk_name] = item["metadata"]["resourceVersion"]
                        else:
                            print("NO RESOURCE VERSION TO PATCH FOR FILE {}".format(os.path.join(manifest_dir, filename)))
                            continue
                    with open(os.path.join(manifest_dir, filename), 'r+') as stream:
                        try:
                            new_docs = []
                            docs = yaml.safe_load_all(stream)
                            for doc in docs:
                                gvk_name = doc["apiVersion"] + doc["kind"] + doc["metadata"]["name"]
                                if gvk_name in resource_version:
                                    print("Patching resource version {}".format(gvk_name))
                                    doc["metadata"]["resourceVersion"] = resource_version[gvk_name]
                                else:
                                    print("NO RESOURCE VERSION TO PATCH FOR {}".format(gvk_name))
                                new_docs.append(doc)
                            stream.seek(0)
                            stream.truncate()
                            yaml.safe_dump_all(new_docs, stream, explicit_start=True)
                        except yaml.YAMLError as exc:
                            print(exc)
                else:
                    print("It's a {}".format(data["kind"]))
                    if "metadata" in data and "resourceVersion" in data["metadata"]:
                        with open(os.path.join(manifest_dir, filename), 'r+') as stream:
                            try:
                                with_resource_version = yaml.safe_load(stream)
                                with_resource_version["metadata"]["resourceVersion"] = data["metadata"]["resourceVersion"]
                                stream.seek(0)
                                stream.truncate()
                                yaml.safe_dump(with_resource_version, stream)
                            except yaml.YAMLError as exc:
                                print(exc)
                    else:
                        print("NO RESOURCE VERSION TO PATCH FOR FILE {}".format(os.path.join(manifest_dir, filename)))
            except yaml.YAMLError as exc:
                print(exc)
