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
from functools import wraps
from google.cloud import datastore
from flask import Flask ,flash, render_template, redirect, url_for, session, make_response, request
from flask_wtf_polyglot import PolyglotForm
from wtforms import StringField, validators, BooleanField, SubmitField, ValidationError, SelectField, PasswordField
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
    submit = SubmitField(u"Tallenna")

class Form(PolyglotForm):
    name    = StringField(u'Joukkueen nimi')
    member1  = StringField(u'Jäsen 1')
    member2  = StringField(u'Jäsen 2')
    member3  = StringField(u'Jäsen 3')
    member4  = StringField(u'Jäsen 4')  
    member5  = StringField(u'Jäsen 5')
    delete = BooleanField(u"Poista joukkue")
    submit = SubmitField(u"Tallenna")
    
    def validate_name(form, field):
        name = field.data.strip().upper()
        if len(name) < 1:
            raise ValidationError("Tyhjä nimi ei kelpaa")
        client = datastore.Client()
        id = session["contest"]
        contest_key = client.key("Kilpailu", int(id))
        contest = client.get(contest_key)
        query = client.query(kind="Sarja", ancestor=contest.key)         
        divisions = list( query.fetch() )
        for d in divisions:
            query = client.query(kind="Joukkue", ancestor=d.key)
            query.add_filter("nimi", "=", field.data)
            teams = list( query.fetch() )
            if len(teams) > 0:
                raise ValidationError("Kilpailussa on samanniminen joukkue")
        return True

    def validate_member1(form, field):
        members = [ v.strip() for k,v in form.data.items() if 'member' in k] 
        while '' in members:
            members.remove('')
        if len(members) < 2:
            raise  ValidationError("Joukkueella oltava vähintään 2 jäsentä")
        if len(members) > len(set(members)):
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
    
    if form.is_submitted():
        if form.delete.data == True:
            client.delete(cp.key)
        elif form.validate():
            code = list(filter(lambda r: r[1] == form.codes.data, control_points))[0]
            cp.update ({
                "aika": data.time.data,
                "koodi": code[1] 
            }) 
            client.put( cp )
        return redirect(url_for("listall"))
    
    return render_template("c.html", form=form)

@app.route('/team/edit/<cid>/<did>/<tid>/', methods=["GET","POST"])
@user
def edit(cid,did,tid):
    client = datastore.Client()   
    team_id = client.key("Kilpailu",int(cid),"Sarja", int(did), "Joukkue", int(tid))
    team = client.get(team_id)
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
        
        if cp.is_submitted():
            data = Cp()
            cp_key = client.key("Leimaus", parent=team_id)
            cp = datastore.Entity(key=cp_key)
            #etsitään id:tä vastaava rastin koodi
            code = list(filter(lambda r: r[0] == data.codes.data, control_points))[0]            
            cp.update ({
                "koodi": code[1], 
                "aika": data.time.data
                }) 
            client.put( cp )
        
    if form.is_submitted():
        #poistetaan joukkue jos on valinta ruksittu
        if form.delete.data == True:
            client.delete(team.key)
        elif form.validate():
            data = list(request.form.values())
            members = []
            name = ""
            for i in range(1,len(data)-1):
                if i == 1:
                    name = data[i]
                elif len(data[i].strip()) > 0:  
                    members.append(data[i].strip())
            team.update( {"nimi": name, "jasenet": members } )
            client.put(team)
        return redirect(url_for("listall"))
        
    return render_template('editform.html', form=form, cp=cp)

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
            results3 = list( query.fetch() ) #sarjan kaikki joukkueet
            for r3 in results3:
                t = { "nimi": r3["nimi"], "jasenet": r3["jasenet"],
                    "id": r3.key.id, "lisaaja": r3["lisaaja"]
                }
                query = client.query(kind="Leimaus", ancestor=r3.key)
                results4 = list(query.fetch()) #joukkueen kaikki leimaukset
                leimaukset = []
                for r4 in results4:
                    leimaukset.append( {"id": r4.key.id , "koodi": r4["koodi"]} )
                t["leimaukset"] = leimaukset
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
    if form.validate_on_submit():
        data = list(request.form.values())
        members = []
        name = ""
        for i in range(1,len(data)-1):
            if i == 1:
                name = data[i]
            elif len(data[i].strip()) > 0:  
               members.append(data[i])
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




















@app.route('/populateCp')
def populateCp():
    client = datastore.Client()
    contest_key = client.key("Kilpailu", 1)
    contest = client.get(contest_key)  
    
    rastit = [
    {"lat": 62.13028, "lon": 25.666688, "koodi": "Tuntematon"}, 
    {"lat": 62.120776, "lon": 25.542413, "koodi": "66"}, 
    {"lat": 62.156532, "lon": 25.496872, "koodi": "6D"}, 
    {"lat": 62.112172, "lon": 25.714338, "koodi": "91"}, 
    {"lat": 62.099795, "lon": 25.544984, "koodi": "48"}, 
    {"lat": 62.133029, "lon": 25.737019, "koodi": "31"}, 
    {"lat": 62.110562, "lon": 25.518665, "koodi": "85"}, 
    {"lat": 62.115047, "lon": 25.615203, "koodi": "69"}, 
    {"lat": 62.088183, "lon": 25.729848, "koodi": "99"}, 
    {"lat": 62.11183, "lon": 25.644512, "koodi": "60"}, 
    {"lat": 62.148123, "lon": 25.618079, "koodi": "63"}, 
    {"lat": 62.134681, "lon": 25.605762, "koodi": "70"}, 
    {"lat": 62.13028, "lon": 25.666688, "koodi": "LAHTO"}, 
    {"lat": 62.10393, "lon": 25.63595, "koodi": "90"}, 
    {"lat": 62.122986, "lon": 25.573049, "koodi": "34"}, 
    {"lat": 62.11906, "lon": 25.628228, "koodi": "37"}, 
    {"lat": 62.089674, "lon": 25.652877, "koodi": "5C"}, 
    {"lat": 62.129767, "lon": 25.626533, "koodi": "44"}, 
    {"lat": 62.086189, "lon": 25.695688, "koodi": "79"}, 
    {"lat": 62.127323, "lon": 25.597278, "koodi": "82"}, 
    {"lat": 62.095187, "lon": 25.628236, "koodi": "64"}, 
    {"lat": 62.141243, "lon": 25.509358, "koodi": "6F"}, 
    {"lat": 62.136462, "lon": 25.668097, "koodi": "41"}, 
    {"lat": 62.153864, "lon": 25.540227, "koodi": "40"}, 
    {"lat": 62.102194, "lon": 25.673997, "koodi": "5A"}, 
    {"lat": 62.144852, "lon": 25.493141, "koodi": "92"}, 
    {"lat": 62.118784, "lon": 25.718561, "koodi": "5B"}, 
    {"lat": 62.121247, "lon": 25.678314, "koodi": "49"}, 
    {"lat": 62.111294, "lon": 25.553191, "koodi": "78"}, 
    {"lat": 62.098636, "lon": 25.691051, "koodi": "56"}, 
    {"lat": 62.078212, "lon": 25.733259, "koodi": "42"}, 
    {"lat": 62.139918, "lon": 25.535011, "koodi": "67"}, 
    {"lat": 62.138397, "lon": 25.56252, "koodi": "7C"}, 
    {"lat": 62.091567, "lon": 25.680401, "koodi": "96"}, 
    {"lat": 62.13232, "lon": 25.498431, "koodi": "53"}, 
    {"lat": 62.132964, "lon": 25.57761, "koodi": "95"}, 
    {"lat": 62.142319, "lon": 25.590916, "koodi": "76"}, 
    {"lat": 62.15146, "lon": 25.50711, "koodi": "46"}, 
    {"lat": 62.126591, "lon": 25.704639, "koodi": "58"}, 
    {"lat": 62.147298, "lon": 25.665822, "koodi": "83"}, 
    {"lat": 62.125561, "lon": 25.558017, "koodi": "51"}, 
    {"lat": 62.087827, "lon": 25.671071, "koodi": "97"}, 
    {"lat": 62.147942, "lon": 25.563169, "koodi": "5E"}, 
    {"lat": 62.124222, "lon": 25.649234, "koodi": "94"}, 
    {"lat": 62.100104, "lon": 25.586932, "koodi": "47"}, 
    {"lat": 62.153364, "lon": 25.52873, "koodi": "74"}, 
    {"lat": 62.099512, "lon": 25.522034, "koodi": "73"}, 
    {"lat": 62.126639, "lon": 25.750133, "koodi": "7B"}, 
    {"lat": 62.141674, "lon": 25.718473, "koodi": "6A"}, 
    {"lat": 62.107914, "lon": 25.61344, "koodi": "43"}, 
    {"lat": 62.093545, "lon": 25.716227, "koodi": "71"}, 
    {"lat": 62.101185, "lon": 25.565572, "koodi": "77"}, 
    {"lat": 62.153435, "lon": 25.560594, "koodi": "33"},
    {"lat": 62.09468, "lon": 25.647515, "koodi": "6E"}, 
    {"lat": 62.100413, "lon": 25.728135, "koodi": "80"},
    {"lat": 62.131251, "lon": 25.540316, "koodi": "7E"},
    {"lat": 62.149572, "lon": 25.597308, "koodi": "68"}, 
    {"lat": 62.134123, "lon": 25.682473, "koodi": "7A"}, 
    {"lat": 62.109962, "lon": 25.7288, "koodi": "89"},
    {"lat": 62.115924, "lon": 25.569589, "koodi": "45"},
    {"lat": 62.135094, "lon": 25.523811, "koodi": "57"},
    {"lat": 62.147825, "lon": 25.513792, "koodi": "38"}, 
    {"lat": 62.113906, "lon": 25.668757, "koodi": "81"},
    {"lat": 62.141654, "lon": 25.628636, "koodi": "50"},
    {"lat": 62.081466, "lon": 25.686679, "koodi": "7D"}, 
    {"lat": 62.108717, "lon": 25.589347, "koodi": "54"}, 
    {"lat": 62.146315, "lon": 25.645642, "koodi": "72"},
    {"lat": 62.095246, "lon": 25.732937, "koodi": "62"},
    {"lat": 62.149229, "lon": 25.576022, "koodi": "86"},
    {"lat": 62.123662, "lon": 25.531059, "koodi": "5D"},
    {"lat": 62.142258, "lon": 25.526039, "koodi": "88"},
    {"lat": 62.144101, "lon": 25.694017, "koodi": "32"},
    {"lat": 62.125632, "lon": 25.49602, "koodi": "6B"},
    {"lat": 62.131769, "lon": 25.669574, "koodi": "MAALI"},
    {"lat": 62.115241, "lon": 25.743788, "koodi": "65"},
    {"lat": 62.093203, "lon": 25.606234, "koodi": "55"},
    {"lat": 62.117266, "lon": 25.694911, "koodi": "75"},
    {"lat": 62.156431, "lon": 25.519131, "koodi": "93"},
    {"lat": 62.147942, "lon": 25.531926, "koodi": "61"}, 
    {"lat": 62.128162, "lon": 25.724837, "koodi": "36"}, 
    {"lat": 62.118778, "lon": 25.524245, "koodi": "39"}, 
    {"lat": 62.115914, "lon": 25.503483, "koodi": "59"}, 
    {"lat": 62.140919, "lon": 25.648821, "koodi": "35"}, 
    {"lat": 62.094023, "lon": 25.661916, "koodi": "84"},
    {"lat": 62.120424, "lon": 25.599044, "koodi": "52"},
    {"lat": 62.131207, "lon": 25.650436, "koodi": "98"},
    {"lat": 62.127514, "lon": 25.674748, "koodi": "5F"}, 
    {"lat": 62.10758, "lon": 25.687644, "koodi": "6C"}
    ]
    entities = []
    for r in rastit:
        cpKey = client.key("Rasti", parent=contest_key)
        cp = datastore.Entity(key=cpKey)
        cp.update ( r )
        entities.append(cp) 
    client.put_multi( entities )
    resp = make_response(str("moi"), 200 )
    resp.charset = "UTF-8"
    resp.mimetype = "text/plain"
    return resp   
    
@app.route('/populateAdmin')
def populateAdmin():
    client = datastore.Client()
    debug = ""
    with client.transaction():
        adminkey = client.key("Admin", 3)
        admin = datastore.Entity(key=adminkey)
        admin.update( {
                "contest": 3,
                "name":"ADMIN",
                "password": "63389e6c25d39357513d0eb0220b2cdb358ca7e689093f67a8d287f03ff85af7c6ccb51287ac64d868b211e4f210c02b2de7b69fc2eb6a47ce9b2c5685e2b137"
                })
        client.put(admin)
    resp = make_response(str("moasdi"), 200 )
    resp.charset = "UTF-8"
    resp.mimetype = "text/plain"
    return resp   
    
@app.route('/populateContest')
def populateContest():
    client = datastore.Client()
    debug = ""
    with client.transaction():

        kilpailut = [
            {"kisanimi":"Jäärogaining", "loppuaika": datetime.strptime("2015-03-17 20:00:00", "%Y-%m-%d %H:%M:%S"), "alkuaika": datetime.strptime("2015-03-15 09:00:00", "%Y-%m-%d %H:%M:%S"), "sarjat": [
                {"sarjanimi":"4 h", "kesto": 4}, 
                {"sarjanimi":"2 h", "kesto": 2}, 
                {"sarjanimi":"8 h", "kesto": 8},
            ]}, 
            {"kisanimi":"Fillarirogaining", "loppuaika": datetime.strptime("2016-03-17 20:00:00", "%Y-%m-%d %H:%M:%S"), "alkuaika": datetime.strptime("2016-03-15 09:00:00", "%Y-%m-%d %H:%M:%S"), "sarjat": [
                {"sarjanimi":"Pääsarja", "kesto": 4}
            ]},
            {"kisanimi":"Kintturogaining", "loppuaika": datetime.strptime("2017-03-18 20:00:00", "%Y-%m-%d %H:%M:%S"), "alkuaika": datetime.strptime("2017-03-18 09:00:00", "%Y-%m-%d %H:%M:%S"),"sarjat": [
                {"sarjanimi":"Pikkusarja", "kesto": 4},
                {"sarjanimi":"Isosarja", "kesto": 8},
    
            ]}]
        entities = []
        count = 1 # tarvitaan, että saadaan valmis id kullekin ruokalajille. id ei saa olla 0
        for kilpailu in kilpailut:
           debug = debug + kilpailu["kisanimi"] + "\n"
           kilpailuKey = client.key("Kilpailu", count)
           count = count + 1
           kilpailuEntity = datastore.Entity(key=kilpailuKey)
           sarjat = kilpailu["sarjat"] #kopioidaan reseptitaulukon viite talteen
           kilpailu.pop('sarjat', None) #poistetaan dictistä reseptitaulukko, koska tallennetaan se erillisenä entiteettina datastoreen
           kilpailuEntity.update ( kilpailu )
           entities.append(kilpailuEntity)       
           for sarja in sarjat:
                sarjaKey = client.key("Sarja", parent=kilpailuKey) # datastore keksii itse id:n
                sarjaEntity = datastore.Entity(key=sarjaKey)
                sarjaEntity.update ( sarja )
                entities.append(sarjaEntity)       
              
        #tallennetaan kaikki kerralla
        client.put_multi( entities )
    #tehdään response, jossa vain dumpataan sisältö näkyville
    resp = make_response( debug + str(kilpailut), 200 )
    resp.charset = "UTF-8"
    resp.mimetype = "text/plain"
    return resp   


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. You
    # can configure startup instructions by adding `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python3_app]
# [END gae_python38_app]

