#!/usr/bin/env python
'''
This module contains utils for generating the rpm spec file and deb changelog from a versions.yml
The versions.yml allows us to have a single place where the versions of this application are
recorded. We use the versions.yml file plus the utils in this module to generate package
changelogs in the formats we need to support (deb, rpm).
'''
import copy
import datetime
import re

# This contains all the necessary version fields and functions to validate
# their values.
#
# The format is:
#   name of field : function to validate the field
#
NECESSARY_FIELDS = {
    "version"     : lambda v: re.match(VERSIONS_RE, v) is not None,
    "time"        : lambda v: validate_date_time(v), # pylint: disable=unnecessary-lambda
    "author"      : lambda v: re.match("[a-zA-Z]+ [a-zA-Z]+", v) is not None,
    "urgency"     : lambda v: re.match("^(low|medium|urgent)$", v) is not None,
    "stability"   : lambda v: re.match("^(unstable|stable)$", v) is not None,
    "description" : lambda v: isinstance(v, list) and all( isinstance(i, str) for i in v ),
    "email"       : lambda v: re.match(
        r"[a-zA-Z+_\-.0-9]+@[a-zA-Z_0-9]+\.[a-zA-Z_0-9]+", v) is not None
}

# The template for each version entry in the changelog.
DEB_CHANGELOG_TEMPLATE="""{name} ({version}) {stability}; urgency={urgency}

{description}

 -- {author} <{email}>  {time}
"""

# The template for each version entry in the markdown changelog.
MARKDOWN_TEMPLATE="""## [{version}] - {time}
{description}
"""

# This is the regex for matching a version string.
# It it written to match python versioning, so there's no dot
# seperating the release candidates the the patch version.
#
# This matches for the following examples
#   1.2.3rc11
#   4.5.6
VERSIONS_RE = re.compile("([0-9]+.[0-9]+.[0-9]+)([a-z]+[0-9]+)?")

def rebuild_version(version, delim="~"):
    '''
    This takes a version string:
        - extracts the pre-release version if there is one.
        - then inserts it again with the given delimiter.
    '''
    version_elems = VERSIONS_RE.match(version)
    if not version_elems:
        raise ValueError(f"Invalid version specified '{version}'")

    version, prelease = version_elems.groups()
    if prelease:
        return f"{version}{delim}{prelease}"

    return version

def build_mkd(outpath, versions):
    '''
    This builds a markdown changelog file, using the information in versions.

    :param output: The file path of the resuling changelog file.
    :param versions: The versioning information.
    '''
    with open(outpath, "w", encoding="utf-8") as outfile:
        print("# Changelog (autogenerated)", file=outfile)
        print(file=outfile)
        for release in versions:
            release = copy.deepcopy(release)
            release["description"] = "\n".join( [ "- " + i for i in release["description"]] )
            release["version"] = rebuild_version(release["version"], delim="-")

            # Convert the date and time to deb format
            dt = datetime.datetime.strptime(release["time"], '%Y/%m/%d %H:%M')
            release["time"] = dt.strftime("%Y-%m-%d")

            print(MARKDOWN_TEMPLATE.format(**(release)), file=outfile)

def build_deb(outpath, versions, name):
    '''
    This builds a debian changelog file, using the information in versions.

    :param output: The file path of the resuling changelog file.
    :param versions: The versioning information.
    '''

    with open(outpath, "w", encoding="utf-8") as outfile:
        for release in versions:
            release = copy.deepcopy(release)
            release["name"] = name
            release["description"] = "\n".join( [ "  * " + i for i in release["description"]] )
            release["version"] = rebuild_version(release["version"], delim="~")

            # Convert the date and time to deb format
            dt = datetime.datetime.strptime(release["time"], '%Y/%m/%d %H:%M')
            release["time"] = dt.strftime("%a, %d %b %Y %H:%M:00")

            print(DEB_CHANGELOG_TEMPLATE.format(**(release)), file=outfile)

def build_rpm(outpath, versions, template):
    '''
    This builds a markdown changelog file, using the information in versions.

    :param output: The file path of the resuling changelog file.
    :param versions: The versioning information.
    :param template: A string template for how the rpm spec file will look.
        The following variables can be used by the spec file template.
            - {version}
            - {upstream_version}
    '''

    upstream_version = versions[0]["version"]
    version = rebuild_version(upstream_version, delim="~")

    # This contains most of the spec file.
    # It's mostly hardcoded in here, if you have any dependencies
    # that need updating, then change them in here.
    #
    # The two main things which are autogenerated are:
    #   - The verion numbers
    #   - The changelog
    #
    with open(outpath, "w", encoding="utf-8") as outfile:
        print(template.format(**locals()), file=outfile)

        changelog_template=\
"""* {time} {author} <{email}> {version}
{description}"""

        for release in versions:
            release = copy.deepcopy(release)
            release["description"] = "\n".join( [ "- " + i for i in release["description"]] )

            version = rebuild_version(release["version"], delim="~")
            release["version"] = version

            # Convert the date and time to rpm format
            dt = datetime.datetime.strptime(release["time"], '%Y/%m/%d %H:%M')
            release["time"] = dt.strftime("%a %b %d %Y")

            print(changelog_template.format(**(release)), file=outfile)
            print(file=outfile)

def validate_date_time(v):
    '''
    :param v: str value to validate.

    This ensures that the given value 'v' correctly matches the datetime format
    we expect.
    '''
    try:
        datetime.datetime.strptime(v, '%Y/%m/%d %H:%M')
    except ValueError as error:
        print(error)
        return False
    return True

def validate_versions(versions):
    '''
    :param versions: A list of releases, where each release is a dictionary
        of release information, such as version, stability, description etc.

    This runs through each field in the versions file validating the fields,
    if there is anything that is not recognised or that doesnt pass
    the validation, then raise an exception.
    '''
    for release in versions:
        for field, value in release.items():
            validator = NECESSARY_FIELDS.get(field)

            if not validator:
                raise ValueError(f"Unrecognised field '{field}'")

            if not validator(value):
                raise ValueError(f"'{field}' does not have correct value "
                                 f"'{value}' or is not formatted correctly.")
