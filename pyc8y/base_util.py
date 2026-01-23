import re


def encode_odata_query_value(value):
    """Encode value strings according to OData query rules.
    http://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#sec_URLParsing
    http://docs.oasis-open.org/odata/odata/v4.01/cs01/abnf/odata-abnf-construction-rules.txt """
    # single quotes escaped through single quote
    return re.sub('\'', '\'\'', value)


def encode_odata_text_value(value):
    """Encode value strings according to OData query rules.
    http://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html#sec_URLParsing
    http://docs.oasis-open.org/odata/odata/v4.01/cs01/abnf/odata-abnf-construction-rules.txt """
    # single quotes escaped through single quote
    encoded_quotes = re.sub('\'', '\'\'', value)
    return encoded_quotes if " " not in encoded_quotes else f"'{encoded_quotes}'"