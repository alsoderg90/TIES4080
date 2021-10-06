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
from datetime import datetime
from functools import wraps
from google.cloud import datastore
from flask import Flask, render_template, redirect, url_for, session, make_response, request
from flask_wtf_polyglot import PolyglotForm
from wtforms import Form, StringField, validators
from authlib.integrations.flask_client import OAuth



# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)
app.secret_key = '!secret'
app.config.from_object('config')

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

class Form(PolyglotForm):
    name    = StringField(u'Joukkueen nimi')
    member1  = StringField(u'Jäsen 1')
    member2  = StringField(u'Jäsen 2')
    member3  = StringField(u'Jäsen 3')
    member4  = StringField(u'Jäsen 4')  
    member5  = StringField(u'Jäsen 5')

def auth(f):
    ''' Tämä decorator hoitaa kirjautumisen tarkistamisen ja ohjaa tarvittaessa kirjautumissivulle
    '''
    @wraps(f)
    def decorated(*args, **kwargs):
        # tässä voisi olla monimutkaisempiakin tarkistuksia mutta yleensä tämä riittää
        if not 'user' in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/edit/<cid>/<did>/<tid>/', methods=["GET","POST"])
@auth
def edit(cid,did,tid):
    client = datastore.Client()
    teamId = client.key("Kilpailu",int(cid),"Sarja", int(did), "Joukkue", int(tid))
    team = client.get(teamId)
    members = []
    for i in range(5):
        if i < len(team["jasenet"]):
            members.append(team["jasenet"][i])
        else:
            members.append("") 
      
    form = Form(data={
        "name": team["nimi"],
        "member1": members[0],
        "member2": members[1],
        "member3": members[2],
        "member4": members[3],
        "member5": members[4]
        })
    return render_template('editform.html', form=form)

@app.route('/list', methods=["GET","POST"])
def listall():
    client = datastore.Client()
    query = client.query(kind="Kilpailu")
    query.order = ["kisanimi"]
    results1 = list( query.fetch() ) # kaikki kilpailut
    a = []
    for r1 in results1:
        c = { "kisanimi": r1["kisanimi"], "sarjat": [], "id":r1.key.id }
        a.append(c)
        query = client.query(kind="Sarja", ancestor=r1.key)
        results2 = list( query.fetch() ) #kilpailun kaikki sarjat
        for r2 in results2:
            d = { "sarjanimi": r2["sarjanimi"], "joukkueet": [], "id":r2.key.id }
            c["sarjat"].append(d)
            query = client.query(kind="Joukkue", ancestor=r2.key)
            results3 = list( query.fetch() ) #kilpailun kaikki sarjat
            for r3 in results3:
                t = { "nimi": r3["nimi"], "jasenet": r3["jasenet"],
                    "id": r3.key.id, "lisaaja": r3["lisaaja"]
                }
                d["joukkueet"].append(t)
    print(a)
    return render_template('list.html', a=a)
    
@app.route('/form', methods=["GET","POST"])
@auth
def form():
    client = datastore.Client()
    if request.method == "POST":
        data = list(request.form.values())
        members = []
        name = ""
        for i in range(len(data)-1):
            if i == 0:
                name = data[i]
            elif len(data[i]) > 0:  
               members.append(data[i])
        print(members)
        #valitaan oikea sarja johon lisätään joukkue
        contestId = session["contest"]
        divisionId = session["division"]
        division_key = client.key("Kilpailu", int(contestId), "Sarja", int(divisionId))
        division = client.get(division_key)
        #luodaan uusi joukkue
        teamKey = client.key("Joukkue", parent=division_key) # datastore keksii itse id:n
        team = datastore.Entity(key=teamKey)
        team.update( {"nimi": name})
        team.update( {"jasenet": members } )
        team.update( {"lisaaja": session["user"]["email"]})
        client.put(team)
    
    form = Form()
    
    return render_template('form.html',form=form)

@app.route('/divisions', methods=["GET","POST"])
@auth
def divisions():
    client = datastore.Client()
    if request.method == "POST":
        id = request.values.get("divisions")
        contest = session["contest"]
        #etsitään datastoresta oikea sarja
        division_key = client.key("Kilpailu", int(contest), "Sarja", int(id))
        division = client.get(division_key)
        session["division"] = division.key.id
        return redirect(url_for("form"))
        
    divisions = session["divisions"]
    return render_template('divisions.html', divisions=divisions)


@app.route('/contests', methods=["GET", "POST"])
@auth
def contests():
    client = datastore.Client()

    if request.method == "POST":
        #etsitään datastoresta oikea kilpailu
        id = request.values.get("contests")
        contest_key = client.key("Kilpailu", int(id))
        contest = client.get(contest_key)
        session["contest"] = contest.key.id
        #etsitään kaikki sarjat datastoresta
        query = client.query(kind="Sarja")
        query.order = ["sarjanimi"]
        results = list( query.fetch() )
        divisions = []
        for r in results:
            # valitaan sarjat jotka kuuluvat oikeaan kilpailuun
            if r.key.parent == contest.key:
                d = {
                    "id": r.key.id,
                    "sarjanimi": r["sarjanimi"]         
                }
                divisions.append(d)
        session["divisions"] = divisions
        return redirect(url_for("divisions"))
        
    query = client.query(kind="Kilpailu")
    query.order = ["kisanimi"]
    results = list( query.fetch() )
    contests = []
    for r in results:
        c = {
            "id": r.key.id,
            "kisanimi": r["kisanimi"]
        }
        contests.append(r)

    user = session.get('user')
    return render_template('contests.html', contests=contests)

@app.route('/')
def home():
    return redirect(url_for("login"))

@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = oauth.google.authorize_access_token()
    user = oauth.google.parse_id_token(token)
    session['user'] = user
    return redirect(url_for("contests"))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')     

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. You
    # can configure startup instructions by adding `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python3_app]
# [END gae_python38_app]

