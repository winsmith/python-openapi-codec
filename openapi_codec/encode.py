import coreapi
from coreapi.compat import urlparse
from openapi_codec.utils import get_method, get_encoding, get_location


def generate_swagger_object(document):
    """
    Generates root of the Swagger spec.
    """
    parsed_url = urlparse.urlparse(document.url)

    swagger = {
        'swagger': '2.0',
        'info': {
            'title': document.title,
            'version': ''  # Required by the spec
        },
        'paths': _get_paths_object(document)
    }

    if parsed_url.netloc:
        swagger['host'] = parsed_url.netloc
    if parsed_url.scheme:
        swagger['schemes'] = [parsed_url.scheme]

    return swagger


def _add_tag_prefix(item):
    operation_id, link, tags = item
    if tags:
        operation_id = tags[0] + '_' + operation_id
    return (operation_id, link, tags)


def _get_links(document):
    """
    Return a list of (operation_id, [tags], link)
    """
    # Extract all the links from the first or second level of the document.
    links = []
    for key, link in document.links.items():
        links.append((key, link, []))
    for key0, obj in document.data.items():
        if isinstance(obj, coreapi.Object):
            for key1, link in obj.links.items():
                links.append((key1, link, [key0]))

    # Determine if the operation ids each have unique names or not.
    operation_ids = [item[0] for item in links]
    unique = len(set(operation_ids)) == len(links)

    # If the operation ids are not unique, then prefix them with the tag.
    if not unique:
        return [_add_tag_prefix(item) for item in links]

    return links


def _get_paths_object(document):
    paths = {}

    links = _get_links(document)

    for operation_id, link, tags in links:
        if link.url not in paths:
            paths[link.url] = {}

        method = get_method(link)
        operation = _get_operation(operation_id, link, tags)
        paths[link.url].update({method: operation})

    return paths


def _get_operation(operation_id, link, tags):
    encoding = get_encoding(link)

    operation = {
        'operationId': operation_id,
        'description': link.description,
        'responses': _get_responses(link),
        'parameters': _get_parameters(link, encoding)
    }
    if encoding:
        operation['consumes'] = [encoding]
    if tags:
        operation['tags'] = tags
    return operation


def _get_parameters(link, encoding):
    """
    Generates Swagger Parameter Item object.
    """
    parameters = []
    properties = {}
    required = []

    for field in link.fields:
        location = get_location(link, field)
        if location == 'form':
            if encoding in ('multipart/form-data', 'application/x-www-form-urlencoded'):
                # 'formData' in swagger MUST be one of these media types.
                parameter = {
                    'name': field.name,
                    'required': field.required,
                    'in': 'formData',
                    'description': field.description,
                    'type': 'string'
                }
                parameters.append(parameter)
            else:
                # Expand coreapi fields with location='form' into a single swagger
                # parameter, with a schema containing multiple properties.
                schema_property = {
                    'description': field.description
                }
                properties[field.name] = schema_property
                if field.required:
                    required.append(field.name)
        elif location == 'body':
            if encoding == 'application/octet-stream':
                # https://github.com/OAI/OpenAPI-Specification/issues/50#issuecomment-112063782
                schema = {'type': 'string', 'format': 'binary'}
            else:
                schema = {}
            parameter = {
                'name': field.name,
                'required': field.required,
                'in': location,
                'description': field.description,
                'schema': schema
            }
            parameters.append(parameter)
        else:
            parameter = {
                'name': field.name,
                'required': field.required,
                'in': location,
                'description': field.description,
                'type': 'string'
            }
            parameters.append(parameter)

    if properties:
        parameters.append({
            'name': 'data',
            'in': 'body',
            'schema': {
                'type': 'object',
                'properties': properties,
                'required': required
            }
        })

    return parameters


def _get_responses(link):
    """
    Returns minimally acceptable responses object based
    on action / method type.
    """
    template = {'description': ''}
    if link.action.lower() == 'post':
        return {'201': template}
    if link.action.lower() == 'delete':
        return {'204': template}
    return {'200': template}
