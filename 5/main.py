# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python38_app]
# [START gae_python3_app]
import os
import json
import hashlib
from datetime import datetime
from operator import itemgetter
from functools import wraps
from google.cloud import datastore
from flask import Flask ,flash, render_template, redirect, url_for, session, make_response, request
from flask_wtf_polyglot import PolyglotForm
from wtforms import StringField, validators, BooleanField, SubmitField, ValidationError, SelectField, PasswordField, HiddenField
from wtforms.fields.html5 import DateTimeLocalField
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)
app.secret_key = '!secret'
app.config.from_object('config')
csrf = CSRFProtect(app)

CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth = OAuth(app)
oauth.register(
    name='google',
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid email profile'
#        'scope': 'openid' #käytä tätä, jos et tarvitse profiilitietoja ja sähköpostia 
    }
)

def user(f):
    ''' Tämä decorator hoitaa kirjautumisen tarkistamisen ja ohjaa tarvittaessa kirjautumissivulle
    '''
    @wraps(f)
    def decorated(*args, **kwargs):
        if not 'user' in session:
           return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/home')
@user
def home():
    return render_template("home.xhtml")

@app.route('/')
def login():
    redirect_uri = url_for('auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = oauth.google.authorize_access_token()
    user = oauth.google.parse_id_token(token)
    session['user'] = user
    return redirect(url_for("home"))

@app.route('/logout/')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. You
    # can configure startup instructions by adding `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python3_app]
# [END gae_python38_app]


