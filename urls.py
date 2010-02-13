from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users

# Local
import handlers
import models

SITE_ROUTES = [
    ('(.+)/+$', handlers.SlashRedirectHandler),
    ('/(\d{4})(?:/(\d{2}))?', handlers.DateHandler),
    ('/(archives?)?(feed)?$', handlers.RootHandler),
    ('(.+?)$', handlers.SiteHandler)
]

ADMIN_ROUTES = [
    ('/admin', handlers.AdminBaseHandler),
    ('/admin/item(?:/?(\d+))?', handlers.ItemHandler),
    ('/admin/settings', handlers.SettingsHandler)
]
ADMIN_ROUTES.extend(SITE_ROUTES)

def main():
    application = webapp.WSGIApplication(SITE_ROUTES, debug=False)

    if users.is_current_user_admin():
        # Enable admin urls for admin
        application = webapp.WSGIApplication(ADMIN_ROUTES, debug=True)

    run_wsgi_app(application)

if __name__ == "__main__":
    main()
