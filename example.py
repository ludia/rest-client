from pprint import pprint
import logging

from rest_client import RestClient

logging.basicConfig(level=logging.ERROR)

if __name__ == '__main__':
    client = RestClient('http://jsonplaceholder.typicode.com',
                        auth=('username', 'password'),
                        options={'timeout': 3.0},
                        user_agent='PlaceHolderClient/1.0')

    print "\n=== PUT /posts/1 ==="
    response = client.call('PUT', ('posts', 1))
    pprint(response.json())

    print "\n=== GET /comments?postId=1 ==="
    response = client.call('GET', ('comments',), params=dict(postId=1))
    pprint(response.json())
