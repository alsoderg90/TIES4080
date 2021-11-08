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

class Cp(PolyglotForm):
    codes = SelectField(u'Rastin koodi', coerce=int)
    time = DateTimeLocalField(u"Leimausaika", format='%Y-%m-%dT%H:%M', default=datetime.now(), render_kw={"step": "1"})
    delete = BooleanField(u"Poista Leimaus")
    submit1 = SubmitField(u"Tallenna")

class Form(PolyglotForm):
    name    = StringField(u'Joukkueen nimi')
    division = SelectField("Sarja" , coerce = int, validators=[validators.Optional()])
    member1  = StringField(u'Jäsen 1')
    member2  = StringField(u'Jäsen 2')
    member3  = StringField(u'Jäsen 3')
    member4  = StringField(u'Jäsen 4')  
    member5  = StringField(u'Jäsen 5')
    delete = BooleanField(u"Poista joukkue")
    submit2 = SubmitField(u"Tallenna")
    contest = HiddenField(u"Contest")
    
    def validate_name(form, field):
        name = field.data.strip().upper()
        if len(name) < 1:
            raise ValidationError("Tyhjä nimi ei kelpaa")
        client = datastore.Client()
        id = form.contest.data
        contest_key = client.key("Kilpailu", int(id))
        contest = client.get(contest_key)
        query = client.query(kind="Sarja", ancestor=contest.key)         
        divisions = list( query.fetch() )
        teams = []
        for d in divisions:
            query = client.query(kind="Joukkue", ancestor=d.key)
            teams.extend([t["nimi"].strip().upper() for t in list( query.fetch() )])
        #poistetaan listasta valittu joukkue
        try:
            teams.remove(session["team"].strip().upper())
        except Exception as e:
            print(e)
        if name in teams:
            raise ValidationError("Kilpailussa on samanniminen joukkue")
        return True

    def validate_member1(form, field):
        members = [ v.strip().upper() for k,v in form.data.items() if 'member' in k] 
        while '' in members:
            members.remove('')
        if len(members) < 2:
            raise  ValidationError("Joukkueella oltava vähintään 2 jäsentä")
        elif len(members) > len(set(members)):
            raise ValidationError("Ei samannimisiä jäseniä")
        return True
        
def user(f):
    ''' Tämä decorator hoitaa kirjautumisen tarkistamisen ja ohjaa tarvittaessa kirjautumissivulle
    '''
    @wraps(f)
    def decorated(*args, **kwargs):
        if not 'user' in session:
           return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin(f):
    ''' Tämä decorator tarkistaa onko kirjauduttu ylläpitäjänä
    '''
    @wraps(f)
    def decorated(*args, **kwargs):
        if not 'admin' in session:
            return redirect(url_for('listall'))
        return f(*args, **kwargs)
    return decorated

@app.route('/cp/edit/<cid>/<did>/<tid>/<lid>/', methods=["GET","POST"])
@admin
@user
def cp(cid,did,tid,lid):
    client = datastore.Client()
    #haetaan oikea leimaus
    cp_id = client.key("Kilpailu",int(cid),"Sarja", int(did), "Joukkue", int(tid), "Leimaus", int(lid))
    cp = client.get(cp_id)
    #Haetaan rastit
    query = client.query(kind="Rasti")
    query.order = ["koodi"]
    results = list( query.fetch() )
    control_points = []
    for r in results:
        control_points.append( (r.key.id, r["koodi"]))
    index = list(filter(lambda r: r[1] == cp["koodi"], control_points))[0]
    form = Cp(codes=index[0], time=cp["aika"])    
    form.time.default = cp["aika"]
    form.codes.choices = control_points
    # Tarkistetaan että oikeaa painiketta painetaan ja syötetyt tiedot ovat valideja
    if form.submit1.data and form.is_submitted():
        if form.delete.data == True:
            client.delete(cp.key)
        elif form.validate():
            code = list(filter(lambda r: r[0] == form.codes.data, control_points))[0]
            print(code)
            cp.update ({
                "aika": form.time.data,
                "koodi": code[1] 
            }) 
            client.put( cp )
        return redirect(url_for("listall"))
    
    return render_template("c.html", form=form)

@app.route('/team/edit/<cid>/<did>/<tid>/', methods=["GET","POST"])
@user
def edit(cid,did,tid):
    client = datastore.Client() 
    #Haetaan tietokannasta oikea joukkue
    team_key = client.key("Kilpailu",int(cid),"Sarja", int(did), "Joukkue", int(tid))
    team = client.get(team_key)
    members = []
    for i in range(5):
        if i < len(team["jasenet"]):
            members.append(team["jasenet"][i])
        else:
            members.append("") 
    session["team"] = team["nimi"]
    #haetaan kilpailun sarjat
    contest_key = client.key("Kilpailu", int(cid))
    contest = client.get(contest_key)
    query = client.query(kind="Sarja", ancestor=contest.key)
    results = list( query.fetch() ) #kilpailun kaikki sarjat
    divisions = []
    for r in results:
        divisions.append((r.key.id, r["sarjanimi"]))
    #etsitään listasta oikea sarja
    division = list(filter(lambda d: int(d[0]) == int(did), divisions))[0]
    print(division)
    #lisätään lomakkeelle joukkueen vanhat tiedot  
    form = Form(data={
        "name": team["nimi"],
        "member1": members[0],
        "member2": members[1],
        "member3": members[2],
        "member4": members[3],
        "member5": members[4],
        "contest": cid
        }, division = division[0])
    form.division.choices = divisions
    cp = None
    if "admin" in session:
        #Haetaan kilpailun rastit
        id = session["contest"]
        contest_key = client.key("Kilpailu", int(id))
        contest = client.get(contest_key)
        query = client.query(kind="Rasti", ancestor=contest.key)
        result = list(query.fetch())
        control_points = []
        for r in result:
            control_points.append((r.key.id, r["koodi"]))
        cp = Cp()  
        cp.codes.choices = control_points 
        if cp.submit1.data and cp.is_submitted():
            data = Cp()
            cp_key = client.key("Leimaus", parent=team_key)
            cp = datastore.Entity(key=cp_key)
            #etsitään id:tä vastaava rastin koodi
            code = list(filter(lambda r: r[0] == data.codes.data, control_points))[0]            
            cp.update ({
                "koodi": code[1], 
                "aika": data.time.data
                }) 
            client.put( cp )
            return redirect(url_for("listall"))       
        
    if form.submit2.data and form.is_submitted():
        #poistetaan joukkue jos on valinta ruksittu
        if form.delete.data == True:
            client.delete(team.key)
            return redirect(url_for("listall"))
        elif form.validate():
            data = request.form
            members = []
            name = data.get("name", None)
            division = data.get("division", None)
            for d in data:
                if d.startswith("member"):
                    value = data.get(d,None)
                    if value != "":
                        members.append(value)
            #etsitään oikea sarja
            division_key = client.key("Kilpailu", int(cid), "Sarja", int(division))
            #luodaan uusi joukkue
            new_key = client.key("Joukkue", parent=division_key) # datastore keksii itse id:n
            new = datastore.Entity(key=new_key)            
            new.update( { "nimi": name, "jasenet": members, "lisaaja": team["lisaaja"] } )
            client.put(new)
            #etsitään joukkueeseen liittyvät leimaukset
            query = client.query(kind="Leimaus", ancestor=team_key)
            results = list( query.fetch() )
            #luodaan joukkueelle uudet leimaukset
            for r in results:
                print(new.key)
                new_cp_key = client.key("Leimaus", parent=new.key)
                new_cp = datastore.Entity(key=new_cp_key)
                new_cp.update( {"aika": r["aika"] , "koodi": r["koodi"] } )
                client.put(new_cp)
                client.delete(r.key) #poistetaan vanha leimaus
            #poistetaan vanha joukkue
            client.delete(team.key)
            return redirect(url_for("listall"))
        
    return render_template('editform.html', form=form, cp=cp)

@app.route('/list', methods=["GET","POST"])
@user
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
            results3 = list( query.fetch() ) #sarjan kaikki joukkueet
            for r3 in results3:
                t = { "nimi": r3["nimi"], "jasenet": sorted(r3["jasenet"]),
                    "id": r3.key.id, "lisaaja": r3["lisaaja"]
                }
                query = client.query(kind="Leimaus", ancestor=r3.key)
                results4 = list(query.fetch()) #joukkueen kaikki leimaukset
                leimaukset = []
                for r4 in results4:
                    leimaukset.append( {"id": r4.key.id , "koodi": r4["koodi"], "aika": r4["aika"]} )
                t["leimaukset"] = sorted(leimaukset, key=lambda t: t["aika"])
                d["joukkueet"].append(t)
            d["joukkueet"] = sorted(d["joukkueet"], key = lambda i: i['nimi']) #lajitellaan joukkueet nimen mukaan
        c["sarjat"] = sorted(c["sarjat"], key = lambda i: i['sarjanimi']) #lajitellaan sarjat nimen mukaan
    #valitaan template sen perusteella ollaanko admin- vai normaalitilassa
    template = "list.html"
    if 'admin' in session:
        template = "adminlist.html"
    return render_template(template, a=a)
    
@app.route('/form', methods=["GET","POST"])
@user
def form():
    client = datastore.Client()
    form = Form()
    form.contest.data = session["contest"]
    if form.validate_on_submit():
        data = request.form
        members = []
        name = data.get("name", None)
        for d in data:
            if d.startswith("member"):
                value = data.get(d,None)
                if value != "":
                    members.append(value)
        #valitaan oikea sarja johon lisätään joukkue
        contest_id = session["contest"]
        division_id = session["division"]
        division_key = client.key("Kilpailu", int(contest_id), "Sarja", int(division_id))
        division = client.get(division_key)
        #luodaan uusi joukkue ja lisätään datastoreen
        team_id = client.key("Joukkue", parent=division_key) # datastore keksii itse id:n
        team = datastore.Entity(key=team_id)
        team.update( {"nimi": name})
        team.update( {"jasenet": members } )
        team.update( {"lisaaja": session["user"]["email"]})
        client.put(team)
        return redirect(url_for("listall"))
    
    return render_template('form.html',form=form)

@app.route('/divisions', methods=["GET","POST"])
@user
def divisions():
    client = datastore.Client()
    if request.method == "POST":
        id = request.values.get("division")
        contest = session["contest"]
        #etsitään datastoresta oikea sarja
        division_key = client.key("Kilpailu", int(contest), "Sarja", int(id))
        division = client.get(division_key)
        session["division"] = division.key.id
        return redirect(url_for("form"))
  
    divisions = session["divisions"]
    class Divisions(PolyglotForm):
        division = SelectField(u"Sarja", choices = divisions, coerce=int)
        submit = SubmitField(u"Valitse")
    form = Divisions()
    
    return render_template('divisions.html', form=form)

@app.route('/contests', methods=["GET", "POST"])
@user
def contests():
    client = datastore.Client()
    if request.method == "POST":
        #etsitään datastoresta oikea kilpailu
        id = request.values.get("contest")
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
                d = (r.key.id, r["sarjanimi"])         
                divisions.append(d)
        session["divisions"] = divisions
        return redirect(url_for("divisions"))
    #haetaan kaikki tietokannassa olevat kilpailut    
    query = client.query(kind="Kilpailu")
    query.order = ["kisanimi"]
    results = list( query.fetch() )
    contests = []
    for r in results:
        c = (r.key.id, r["kisanimi"])
        contests.append(c)
        
    class Contests(PolyglotForm):
        contest = SelectField(u"Kilpailu", choices = contests, coerce=int)
        submit = SubmitField(u"Valitse")
    form = Contests()
    
    return render_template('contests.html', form=form)

@app.route('/admin', methods = ["GET","POST"])
@user
def admin():
    #kilpailu täytyy valita ensin
    if not "contest" in session:
        return redirect(url_for("contest"))
    client = datastore.Client()
    class Login(PolyglotForm):
        username   = StringField(u"Tunnus")
        password = PasswordField(u'Salasana')
        submit = SubmitField(u"Kirjaudu sisään")
    form = Login()
    
    if form.is_submitted():
        username = form.username.data
        password = form.password.data
        #luodaan syötetystä salasanasta tiiviste
        m = hashlib.sha512()
        m.update(str(password).encode("UTF-8"))
        password = m.hexdigest()
        #haetaan kilpailukohtainen käyttäjätunnus
        admin_key = client.key("Admin", int(session["contest"]))
        admin = client.get(admin_key)
        if admin["password"] == password and admin["name"].upper().strip() == username.upper().strip():
            session["admin"] = True
            return redirect(url_for("listall"))
        else:
            flash("Kirjautuminen epäonnistui")
      
    return render_template("admin.html", form = form)    

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

@app.route('/logout/admin')
#@user
def logoutadmin():
    session.pop("admin",None)
    return redirect(url_for("listall"))

@app.route('/logout/user')
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


