from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext.webapp import template

import logging
import models
import os

class SlashRedirectHandler(webapp.RequestHandler):
    """Strip off slashes and permanent redirect to the slashless path"""
    def get(self, path):
        self.redirect(path, permanent=True)

class DateHandler(webapp.RequestHandler):
    """Redirect to the main archive page, with a hash for the year/month"""
    def get(self, year, month=None):
        url = '/archive#y-' + year
        if month:
            url += '-m-%s' % int(month)

        self.redirect(url)

class BaseHandler(webapp.RequestHandler):
    """Base handler, provides render_template_to_response/string with default parameters"""

    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

    def render_text_to_response(self, text, content_type=None):
        # App engine uses text/html and utf-8 by default
        # http://code.google.com/appengine/docs/python/tools/webapp/buildingtheresponse.html
        if content_type != None:
            self.response.content_type = content_type

        self.response.out.write(text)

    def render_template_to_response(self, template_name='index', values={}, format='html'):
        html, content_type = self.render_template(template_name, values, format)
        self.render_text_to_response(html, content_type)

    def render_template(self, template_name='index', values={}, format='html'):
        values.update({
            'settings': models.Setting.get_dictionary()
        })

        content_type = None
        if format == 'feed':
            content_type = 'application/atom+xml; charset=utf-8'

        template_path = os.path.join(self.template_dir, template_name + '.' + format)
        html = template.render(template_path, values)

        return html, content_type

class SiteHandler(BaseHandler):
    """Handle the audience-facing side of the site"""

    def get(self, slug):
        item = models.Item.get_by_slug(slug)
        if not item:
            return self.redirect_or_404(slug)

        self.render_template_to_response('item', {
            'item': item,
            'title': item.title
        })

    def redirect_or_404(self, slug):
        """Find out if the slug was previously used. If so, redirect. Otherwise, 404"""
        alias = models.Alias.get_by_slug(slug)
        if alias and alias.item.is_published:
            self.redirect(alias.item.slug, permanent=True)
        else:
            self.error(404)
            self.render_template_to_response('404', {
                'path': slug,
                'title': "Not Found"
            })

class RootHandler(SiteHandler):
    """Handle the root element"""
    def get(self):
        html = memcache.get('root_html')

        # Cache miss
        if not html:
            root, posts = self.root_and_posts()
            html, _ = self.render_template('base', {
                'item': root,
                'posts': posts.fetch(10)
            })
            memcache.set('root_html', html)

        self.render_text_to_response(html)

    @classmethod
    def root_and_posts(klass):
        root = models.Item.get_by_slug('/')
        posts = models.Item.all_published_posts()
        return root, posts

class ArchiveHandler(RootHandler):
    def get(self):
        html = memcache.get('archive_html')

        if not html:
            root, posts = self.root_and_posts()
            html, _ = self.render_template('archive', {
                'item': root,
                'posts': posts
            })
            memcache.set('archive_html', html)

        self.render_text_to_response(html)

class FeedHandler(RootHandler):
    def get(self):
        # When feedburner is enabled, only give feedburner bot access
        # to the feed, all others get redirected
        feed_address = models.Setting.get_dictionary()['feedburner_address']
        if feed_address:
            userAgent = self.request.headers.get('User-Agent', '')
            if not 'feedburner' in userAgent:
                return self.redirect(feed_address)

        root, posts = self.root_and_posts()

        # Render the feed
        self.render_template_to_response('atom', {
            'item': root,
            'posts': posts.fetch(10)
        }, 'feed')
