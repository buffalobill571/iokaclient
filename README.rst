iokaclient
=============

.. start-inclusion-marker-do-not-remove

.. image:: https://github.com/buffalobill571/iokaclient/workflows/CI/badge.svg?event=push
   :alt: Build Status
   :target: https://github.com/buffalobill571/iokaclient/actions?query=event%3Apush+branch%3Amaster+workflow%3ACI


Ioka python client, supports both synchronous and asynchronous operations.

Installation
------------

Run ``pip install -i https://test.pypi.org/simple/ iokaclient``.

Reasoning
---------

Unlike other available clients, this one:

- Supports modern Python versions
- Does not use `global variables <https://stackoverflow.com/questions/19158339/why-are-global-variables-evil>` for set up
- Supports both synchronous and asynchronous ways of doing operations
- Uses connection pooling
- Stricly linted
- Supports ORM like interactivity for Order instance
- Strongly typed and highly predictable according to API specification
- Will be tested with 100% coverage... soon :)
- Uses only Python standart lib, except HTTP client


Configuration
-------------

Create client, using api key and endpoint url:

.. code: python

    import ioka

    client = ioka.Ioka(api_key=..., base_url=...)
