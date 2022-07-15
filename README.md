# Python_Cloud_Client
A python module which will allow a user to access the onscale cloud functionality via a python interface

## Contents
* [Installation](#install)
* [Dev Setup](#setup)
* [Configuration](#config)
* [Publishing the Python Libraries](#publish)
* [Code Standards](#codestd)
    * [Linting and Unit Test](#lint)
* [Doc Generation](#docs)


<a name="install"></a>
## Installation

These instructions are for end user installation. For editable development installs from source, see the [Dev Setup](#setup) section.

Installs can be done through the python package manager `pip`; just include the url for the onscale private PyPI server.

* Install `onscale_client` (Cloud Client) library:
```
pip install --extra-index-url https://pypi.portal.onscale.com onscale_client
```

* To update a library to the latest version (example `onscale_client`):
```
pip install --upgrade --extra-index-url https://pypi.portal.onscale.com onscale_client
```


<a name="setup"></a>
## Dev Setup

To develop in this repository found in `packages/`, a few tools to install:
* Python 3.7+ with `pip`

# Generating REST API Data Model
To update the REST API data model found in `onscale_client/api/datamodel.py`, run:
```
./scripts/generate_api.sh
```

This script will generate the data model based upon the `/scripts/swagger.json` file which can be downloaded from `portal.onscale.com/doc/`.

The cloud client can be installed in "editable" mode for development:
```
pip install -e "packages/cloud_client[dev]"
```

### Python
You're free to install Python however you choose. I wrote a [quick guide here](https://gist.github.com/kykosic/954a59dc8a3544c0cf969b792ce1bc62) on how to setup Python development environments via `conda` if you don't know how to properly do this.


### Python Libraries
Each library can be installed via pip in Python 3.7. For example, to install `onscale_client`:
```
pip install packages/cloud_client
```
To install in inplace for development and include dev dependencies:
```
pip install -e 'packages/cloud_client[dev]'
```


<a name="config"></a>
## Configuration

Once installed, a user profile and developer token will need to be created using OnScale login credentials.  This can be done using the configure process within the onscale_client module for the desired portal.
```
import onscale_client as cloud
cloud.configure(portal_target='dev')
```


<a name="publish"></a>

## Publishing the Python Libraries

Please see the `Simulation_API` repository `README.md` file for full details on publishing the python libraries.


<a name="codestd"></a>
## Code Standards
General philosophy for development on this project should be:
* Intuitive user experience
* Concise "Pythonic" syntax
* Consistency with open-source libraries, particularly NumFOCUS

For more information on development best practices and code style in this repository, see [the Style Guide](StyleGuide.md).

#### Syntax RFC
Large additions and changes to the Python syntax should go through an open RFC discussion prior to implementation, see [the Syntax RFC Process](SyntaxRFCProcess.md).


<a name="lint"></a>
### Linting and Unit Tests
Linting can be run via `flake8` using the script:
```
./scripts/lint.sh
```


<a name="docs"></a>
## Doc Generation
Python API documentation is auto-generated from function type annotations and docstrings. The classes and methods which are documented are configured in the `./doc/source` directory. The documents can be generated with `sphinx` with:
```
cd packages/cloud_client/doc/
make html
```
This will output the HTML static documentation to `doc/build/html/index.html`.