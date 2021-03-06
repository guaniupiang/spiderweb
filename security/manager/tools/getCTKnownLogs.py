#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Parses a JSON file listing the known Certificate Transparency logs
(as downloaded from https://www.certificate-transparency.org/known-logs)
and generates a C++ header file to be included in Firefox.
"""

from __future__ import print_function
from string import Template
import argparse
import base64
import json
import os.path
import sys
import textwrap
import urllib2


OUTPUT_TEMPLATE = """\
/* -*- Mode: C++; tab-width: 8; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/* vim: set ts=8 sts=2 et sw=2 tw=80: */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* This file was automatically generated by $prog. */

#ifndef $include_guard
#define $include_guard

#include <stddef.h>

struct CTLogInfo {
  const char* const logName;
  const char* const logUrl;
  const char* const logKey;
  const size_t logKeyLength;
};

const CTLogInfo kCTLogList[] = {
$logs
};

#endif // $include_guard
"""


def get_hex_lines(blob, width):
    """ Convert a binary string to a multiline text of C escape sequences. """
    text = "".join(["\\x{:02x}".format(ord(c)) for c in blob])
    # When escaped, a single byte takes 4 chars (e.g. "\x00").
    # Make sure we don't break an escaped byte between the lines.
    return textwrap.wrap(text, width - width % 4)


def get_log_info_structs(json_data):
    """ Return array of CTLogInfo initializers for the known logs. """
    tmpl = Template(textwrap.dedent("""\
          { $description,
            $url,
        $indented_log_key,
            $log_key_len }"""))
    initializers = []
    for log in json_data["logs"]:
        log_key = base64.decodestring(log["key"])
        initializers.append(tmpl.substitute(
            # Use json.dumps for C-escaping strings.
            # Not perfect but close enough.
            description=json.dumps(log["description"]),
            url=json.dumps("https://{0}/".format(log["url"])),
            # Maximum line width is 80.
            indented_log_key="\n".
            join(['    "{0}"'.format(l) for l in get_hex_lines(log_key, 74)]),
            log_key_len=len(log_key)))
    return initializers


def generate_cpp_header_file(json_data, out_file):
    """ Generate the C++ header file for the known logs. """
    filename = os.path.basename(out_file.name)
    include_guard = filename.replace(".", "_").replace("/", "_")
    log_info_initializers = get_log_info_structs(json_data)
    out_file.write(Template(OUTPUT_TEMPLATE).substitute(
        prog=os.path.basename(sys.argv[0]),
        include_guard=include_guard,
        logs=",\n".join(log_info_initializers)))


def run(args):
    """
    Load the input JSON file and generate the C++ header according to the
    command line arguments.
    """
    if args.file:
        print("Reading file: ", args.file)
        with open(args.file, "rb") as json_file:
            json_text = json_file.read()
    elif args.url:
        print("Fetching URL: ", args.url)
        json_request = urllib2.urlopen(args.url)
        try:
            json_text = json_request.read()
        finally:
            json_request.close()

    json_data = json.loads(json_text)

    print("Writing output: ", args.out)

    with open(args.out, "w") as out_file:
        generate_cpp_header_file(json_data, out_file)

    print("Done.")


def parse_arguments_and_run():
    """ Parse the command line arguments and run the program. """
    arg_parser = argparse.ArgumentParser(
        description="Parses a JSON file listing the known "
        "Certificate Transparency logs and generates "
        "a C++ header file to be included in Firefox.",
        epilog="Example: python %s --url" % os.path.basename(sys.argv[0]))

    source_group = arg_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file",
                              help="Read the known CT logs JSON file from the "
                              "specified location on the filesystem.")
    source_group.add_argument("--url", nargs="?",
                              const="https://www.certificate-transparency.org/"
                              "known-logs/log_list.json",
                              help="Download the known CT logs JSON file "
                              "from the specified URL. "
                              "If no URL is given, download the file "
                              "from %(const)s.")

    arg_parser.add_argument("--out",
                            default="../../certverifier/CTKnownLogs.h",
                            help="Path and filename of the header file "
                            "to be generated. Defaults to %(default)s")

    run(arg_parser.parse_args())


if __name__ == "__main__":
    parse_arguments_and_run()
