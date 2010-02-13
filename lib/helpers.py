"""Miscellaneous helper functions"""
import datetime
import re

# Fix path before markdown and pygments imports
import os
import sys
#sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'markdown'))
#sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pygments'))
sys.path.insert(0, os.path.dirname(__file__))

import markdown
# Import now, otherwise markdown doesn't find it due to appEngine issues ...
import pygments

DATE_REGEX = re.compile(\
    '(?P<year>\d{4})[ -/.]?(?P<month>\d{2})[ -/.]?(?P<day>\d{2})')

# Used for title/slug replacement
HTML_TAGS = re.compile('<[^.]*?>')
ENTITIES = re.compile('&[^;]{1,8};')
WHITESPACE_REGEX = re.compile('\s+')
SLUG_BLACKLIST = re.compile('[^a-z0-9\-/]')
SLASH_REGEX = re.compile('/+')
DASH_REGEX = re.compile('-+')
DASH_ADJACENT_TO_SLASH = re.compile('-*/-*')
INITIAL_SLASH_DASH = re.compile('^[/\-]+|[\/-]+$')

def process_content(text, fallback_date=None):
    r"""
    Process a block of content text, extracting fields and converting to
    HTML (using Markdown/Textile). Also return a normalized content block
    with fields filled in.

    fallback_date Year attribute is used as a prefix for slug generation

    >>> content = u'\nHello World!\n\nThis is my *first* post!'
    >>> year = datetime.date.today().year
    >>> html, data = process_content(content, datetime.date(2010, 10, 10))
    >>> html
    u'<p>Hello World!</p>\n<p>This is my <em>first</em> post!</p>'

    If metadata is not specified, it is extracted from the body of the post

    >>> 'title' in data and data['title']
    u'Hello World!'
    >>> 'slug' in data and data['slug']
    u'/2010/hello-world'

    Metadata can be specified using the Meta-Data syntax from MultiMarkdown

    >>> content = u'title: My Post Title\nslug: 2009/slug-name\ndate: 20091015\n\nThis is my post!'
    >>> html, data = process_content(content)
    >>> data['slug']
    u'/2009/slug-name'
    >>> data['title']
    u'My Post Title'
    >>> (data['date'].year, data['date'].month, data['date'].day)
    (2009, 10, 15)
    >>> html
    u'<p>This is my post!</p>'
    """
    # Create converter
    md_processor = markdown.Markdown(
        ['footnotes', 'fenced_code', 'codehilite', 'tables', 'toc', 'meta'])

    # Process content
    html = md_processor.convert(text)
    # Get metadata
    data = md_processor.Meta

    # Convert the date, if there
    if 'date' in data:
        data['date'] = parse_datetime(data['date'][0])

    # Pick up remaining fields
    if 'title' in data:
        # Take only first value
        data['title'] = titleize(data['title'][0])
    else:
        # Take the first line of HTML as the title
        data['title'] = titleize(html.splitlines()[0])

    if 'slug' in data:
        # Take only first value
        data['slug'] = slugify(data['slug'][0])
    else:
        # Generate a slug
        if 'date' in data:
            date = data['date']
        elif fallback_date:
            date = fallback_date
        else:
            date = datetime.date.today()

        data['slug'] = slugify("%s/%s" % (date.year, data['title']))

    return html, data

def slugify(text):
    """Convert the string into a slug-safe format

    >>> slugify('/hello/')
    '/hello'

    >>> slugify(' I LOVE!! CHEESE & QUESO?')
    '/i-love-cheese-queso'

    >>> slugify('&quot;Cool&quot;')
    '/cool'

    >>> slugify('//// he_llo ///--/-/ world----')
    '/hello/world'

    >>> slugify('/')
    '/'
    """
    # Lowercase, remove whitespace and replace with -
    slug = WHITESPACE_REGEX.sub('-', text.lower().strip())
    # Strip entities
    slug = ENTITIES.sub('', slug)
    # Remove non-whitelist characters
    slug = SLUG_BLACKLIST.sub('', slug)
    # Remove dash before/after slash
    slug = DASH_ADJACENT_TO_SLASH.sub('/', slug)
    # Convert multiple slashes & dashes into one
    slug = DASH_REGEX.sub('-', slug)
    slug = SLASH_REGEX.sub('/', slug)
    # Remove beginning and ending slashes & dashes
    slug = INITIAL_SLASH_DASH.sub('', slug)
    return '/' + slug

def titleize(text, character_limit=140, ellipsis='...'):
    """Convert the string into plain text suitable for a title

    >>> titleize('Hello <strong>world</strong>!')
    'Hello world!'

    Pass a character limit

    >>> titleize('This title is too long', 15)
    'This title...'
    """
    title = text.strip()
    # Strip HTML tags
    title = HTML_TAGS.sub('', title)
    # Normalize whitespace
    title = WHITESPACE_REGEX.sub(' ', title)
    # Clip length
    if (len(title) > character_limit):
        # Try to find a wordbreak
        last_space = title.rfind(' ', 0, character_limit - len(ellipsis))
        if (last_space != -1):
            title = title[:last_space] + ellipsis
        else:
            title = title[:character_limit - len(ellipsis)] + ellipsis

    return title

def parse_datetime(text):
    """Extract a date from a string, trying variety of formats

    >>> d = parse_datetime('2009 12 24')
    >>> d.year, d.month, d.day
    (2009, 12, 24)
    >>> d = parse_datetime('2008/02/04')
    >>> d.year, d.month, d.day
    (2008, 2, 4)
    >>> d = parse_datetime('1979-10-15')
    >>> d.year, d.month, d.day
    (1979, 10, 15)
    >>> d = parse_datetime('2001.02.02')
    >>> d.year, d.month, d.day
    (2001, 2, 2)
    >>> d = parse_datetime('19800617')
    >>> d.year, d.month, d.day
    (1980, 6, 17)

    Invalid dates return None
    >>> parse_datetime('1999 19 45')
    >>> parse_datetime('1999 00 15')
    >>> parse_datetime('1999 02 95')

    If nothing is found, return None
    >>> parse_datetime('')
    >>> parse_datetime('Cheese is delicious')
    """
    match = DATE_REGEX.search(text)
    if match:
        year, month, day = [x and int(x) for x in match.groups()]
        try:
            return datetime.datetime.now().replace(year, month, day)
        except ValueError:
            pass

    # Couldn't find anything
    return None

# Test when standalone
def _test():
    """Run doctests"""
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()
