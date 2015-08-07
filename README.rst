===========
Rest-Client
===========

.. _description:

REST/JSON client based on Requests.


Usage
=====

.. code-block:: python

   from rest_client import RestClient

   client = RestClient('http://jsonplaceholder.typicode.com',
                       auth=('username', 'password'),
                       options={'timeout': 3.0},
                       user_agent='PlaceHolderClient/1.0')

   # PUT /posts/1
   response = client.call('PUT', ('posts', 1))

   # GET /comments?postId=1
   response = client.call('GET', ('comments',), params=dict(postId=1))

