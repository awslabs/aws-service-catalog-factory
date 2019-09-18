Project Assurance
=================

Assurance
---------

This project has been through an assurance process to ensure the project is:

- valuable to AWS customers
- properly licenced


The same process ensures that there are mechanisms to ensure maintainers are:

- likely able to acceptably support it with regards to being responsive to github issues and pull requests


And finally, at the time of publishing:

- any 3rd party components actually contained in the repo are checked to ensure they are correctly licensed and that we are correctly complying with the open source licenses that apply to those 3rd party components.


Project Management
------------------

Quality Assurance
~~~~~~~~~~~~~~~~~

CICD Process
^^^^^^^^^^^^

Unit tests are run on every commit.  If unit tests fail a release of the project cannot occur.

The project dependencies are scanned on each commit for known vulnerabilities.  If an issue is discovered a release of the project cannot occur.


Review Process
^^^^^^^^^^^^^^

There are regular reviews of the source code where static analysis results and unit test coverage are assessed.


Raising a feature request
~~~~~~~~~~~~~~~~~~~~~~~~~

Product feature requests drive the majority of changes to this project.  If you would like to raise a feature request
please raise a Github issue.


Backwards compatibility
~~~~~~~~~~~~~~~~~~~~~~~

All changes to date have been fully backwards compatible.  Effort will be made to ensure this where possible.


Design consultation
~~~~~~~~~~~~~~~~~~~

When there is a significant addition or change to the internal implementation we consult a limited number of users.
Users are asked to access the potential impact so that we can understand the impact and the potential value of the
change. If you would like to register as such a user please raise a Github issue.

