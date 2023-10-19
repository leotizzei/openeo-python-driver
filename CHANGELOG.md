# Changelog

All notable changes to this project will be documented in this file.

This project does not have a real release cycle (yet).
Upstream projects usually depend on development snapshots of this project.
Still, to have some kind of indicator of small versus big change,
we try to bump the version number (in `openeo_driver/_version.py`)
roughly according to [Semantic Versioning](https://semver.org/).

When adding a feature/bugfix without bumping the version number:
just describe it under the "In progress" section.
When bumping the version number in `openeo_driver/_version.py`
(possibly accompanying a feature/bugfix):
"close" the "In Progress" section by changing its title to the new version number
(and describe accompanying changes, if any, under it too)
and start a new "In Progress" section above it.


## In progress

- Start returning "OpenEO-Costs-experimental" header on synchronous processing responses

## 0.71.0

- `OpenEoBackendImplementation.request_costs()`: add support for passing User object (related to [Open-EO/openeo-geopyspark-driver#531](https://github.com/Open-EO/openeo-geopyspark-driver/issues/531))

## 0.70.0

- Initial support for openeo-processes v2.0, when requesting version 1.2 of the openEO API ([#195](https://github.com/Open-EO/openeo-python-driver/issues/195))
- Drop support for 0.4 version of openeo-processes ([#47](https://github.com/Open-EO/openeo-python-driver/issues/47))


## 0.69.1

- Add backoff to ensure EJR deletion ([#163](https://github.com/Open-EO/openeo-python-driver/issues/163))


## 0.69.0

- Support job deletion in EJR ([#163](https://github.com/Open-EO/openeo-python-driver/issues/163))