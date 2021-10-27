import io
import cgitb
import hashlib
import json
import mysql.connector
import mysql.connector.pooling
from itertools import groupby
from functools import wraps
from flask import Flask, flash, request, render_template, session, redirect, url_for
from flask_wtf_polyglot import PolyglotForm
from wtforms import validators, BooleanField, StringField, SubmitField, PasswordField, SelectField, ValidationError
from wtforms.fields.html5 import DateTimeLocalField
from flask_wtf.csrf import CSRFProtect

cgitb.enable()

with io.open("dbconfig.json", "r", encoding="UTF-8") as file:
    dbconfig = json.load(file)

pool=mysql.connector.pooling.MySQLConnectionPool(pool_name="tietokantayhteydet",
    pool_size=2, #PythonAnywheren ilmaisen tunnuksen maksimi on kolme
    **dbconfig
)

app = Flask(__name__)
app.secret_key = '"s4l41n3n'
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax'
)
csrf = CSRFProtect(app)

class Lomake(PolyglotForm):
    nimi = StringField(u"Nimi")
    salasana = PasswordField(u"Salasana")
    sarja = SelectField("Sarja" , coerce = int, validators=[validators.Optional()])
    jasen1 = StringField(u"Jäsen 1")
    jasen2 = StringField(u"Jäsen 2")
    jasen3 = StringField(u"Jäsen 3")
    jasen4 = StringField(u"Jäsen 4")
    jasen5 = StringField(u"Jäsen 5")
    poista = BooleanField(u"Poista joukkue")
    submit = SubmitField(u"Tallenna")
    #nimi kentän validointi --> Ei hyväksytä tyhjää kenttää, eikä kilpailussa ei saa olla samannimisä joukkueita
    def validate_nimi(form, field):
        jnimi = field.data.strip().upper()
        if len(jnimi) < 1:
            raise ValidationError("Syötä nimi")
        joukkue = ""
        if session["joukkuenimi"] != None:
            joukkue = session["joukkuenimi"]
        try:
            con = pool.get_connection()
            cur = con.cursor(buffered=True, dictionary=True)
            sql = """SELECT joukkueet.joukkuenimi
                FROM sarjat, joukkueet, kilpailut
                WHERE joukkueet.sarja = sarjat.id
                AND joukkueet.joukkuenimi != %s
                AND sarjat.kilpailu = kilpailut.id
		        AND kilpailut.kisanimi = %s;"""
            cur.execute(sql, (joukkue, session["kilpailu"]["kisanimi"]))
            joukkueet = cur.fetchall()
        except:
            con.close()
        finally:
            con.close()
        if any(j["joukkuenimi"].strip().upper() == jnimi for j in joukkueet):
            raise ValidationError("Varattu nimi")
        return True
    #jäsen kentän validointi --> Nimi pitää olla syötettynä vähintään 2 kenttään
    def validate_jasen1(form, field):
        jasenet = [ v.strip() for k,v in form.data.items() if 'jasen' in k]
        while '' in jasenet:
            jasenet.remove('')
        if len(jasenet) < 2:
            raise  ValidationError("Joukkueella oltava vähintään 2 jäsentä")
        return True

#Tarkastetaan onko käyttäjä admin
def admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not('admin' in session):
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated

#Kirjautumisen tarkistus, ja tarvittaessa uudellenohjaus kirjautumissivulle
def user(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not('kirjautunut' in session):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/rasti/<aika>', methods=['GET', "POST"])
def rasti(aika):
    #haetaan leimaus
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        # SELECT DATE_FORMAT(t.aika, '%Y-%m-%d %H:%i:%S') AS aika, t.joukkue, t.rasti
        sql = """SELECT *
            FROM tupa t, rastit r
            WHERE r.id = t.rasti
            AND t.aika = %s
            AND t.joukkue = %s;"""
        cur.execute(sql,(aika,session["joukkue"]["id"]))
        result = cur.fetchone()
        #result["aika"] = datetime.strptime(result["aika"], "%Y-%m-%d %H:%M:%S")
        session["aika"] = result["aika"]
        session["koodi"] = result["rasti"]
    except:
        con.close()
    finally:
        con.close()
    #kaikkien rastien haku
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT *
            FROM rastit;"""
        cur.execute(sql,)
        results = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()

    rastit = []
    for r in results:
        rastit.append((r["id"]+500, r["koodi"]))
    #oikean rastin etsiminen oletusrastiksi
    rasti = list(filter(lambda r: r[0] == result["rasti"]+500, rastit))[0]

    class Rasti(PolyglotForm):
        aika = DateTimeLocalField(u"Aika", format='%Y-%m-%dT%H:%M:%S', render_kw={"step": "1"})
        rasti = SelectField(u"Rasti", coerce = int)
        poista = BooleanField(u"Poista rasti")
        submit = SubmitField(u"Tallenna")
    form = Rasti(aika = result["aika"], rasti = rasti[0])
    form.rasti.choices = rastit

    if form.is_submitted():
        rasti = form.rasti.data-500
        aika = request.form["aika"]
        joukkue = session["joukkue"]["id"]
        aika = aika.replace("T", " ")
        print(aika)
        if form.poista.data == True:
            try:
                con = pool.get_connection()
                cur = con.cursor(buffered=True, dictionary=True)
                sql = """DELETE
                    FROM tupa
                    WHERE joukkue = %s
                    AND aika = %s;"""
                cur.execute(sql, (joukkue,aika))
                con.commit()
            except:
                con.close()
            finally:
                con.close()
        else:
            try:
                con = pool.get_connection()
                cur = con.cursor(buffered=True, dictionary=True)
                sql = """UPDATE tupa
                    SET aika = %s,
                    rasti = %s
                    WHERE joukkue = %s
                    AND aika = %s;"""
                cur.execute(sql, (aika, rasti, joukkue, session["aika"]))
                con.commit()
            except:
                con.close()
            finally:
                con.close()
        return redirect(url_for("adminMuokkaa", joukkuenimi=session["joukkue"]["joukkuenimi"]))
    return render_template("rasti.xhtml", form=form)


@app.route('/rastit/')
@app.route('/rastit/<kilpailunimi>')
@admin
def rastit(kilpailunimi=None):
    if kilpailunimi == None:
         return redirect(url_for("index"))
    id = session["kilpailu"]["id"]
    #haetaan ensin leimatut rastit, jonka jälkeen rastit joita ei ole leimattu
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT COUNT(r.koodi) AS leimauksia, r.koodi, r.lat, r.lon FROM tupa t
            LEFT JOIN rastit r ON (t.rasti = r.id)
            JOIN kilpailut k ON (r.kilpailu = k.id)
            WHERE k.id = %s
            GROUP BY r.koodi
            UNION
            SELECT COUNT(r.koodi)-1 AS leimauksia, r.koodi, r.lat, r.lon FROM tupa t
            RIGHT JOIN rastit r ON (t.rasti = r.id)
            JOIN kilpailut k ON (r.kilpailu = k.id)
            WHERE k.id = %s
            AND t.rasti IS NULL
            GROUP BY r.koodi
            ORDER BY leimauksia DESC;"""
        cur.execute(sql,(id,id))
        rastit = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()

    return render_template("rastit.xhtml", rastit = rastit)

@app.route('/joukkue/')
@app.route('/joukkue/<joukkuenimi>', methods=['GET', "POST"])
@admin
def adminMuokkaa(joukkuenimi=None):
    if joukkuenimi == None:
         return redirect(url_for("sarja", sarjanimi=session["sarjanimi"]))
    joukkueet = session["joukkueet"]
    joukkue = list(filter(lambda j : j["joukkuenimi"] == joukkuenimi, joukkueet))[0]
    jasenet = json.loads(joukkue["jasenet"])
    session["joukkue"] = joukkue
    session["joukkuenimi"] = joukkue["joukkuenimi"]
    if len(joukkue) < 1:
        return redirect(url_for("sarja", sarjanimi=session["sarjanimi"]))
    for i in range(5):
        if (i >= len(jasenet)):
            jasenet.append("")
    #sarjojen haku tietokannasta
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = "SELECT * FROM sarjat;"
        cur.execute(sql,)
        rivit = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()
    #lisätään sarjat alasvetolaatikkoa varten ja etsitään oletussarja
    sarjat = []
    for r in rivit:
        sarjat.append((r["id"]+500, r["sarjanimi"]))
    sarja = list(filter(lambda s: s[0] == joukkue["sarja"]+500, sarjat))[0]

    form = Lomake(data={
        "nimi": joukkuenimi,
        "jasen1":jasenet[0],
        "jasen2":jasenet[1],
        "jasen3":jasenet[2],
        "jasen4":jasenet[3],
        "jasen5":jasenet[4],
        }, sarja = sarja[0])
    form.sarja.choices = sarjat
    #haetaan joukkueen rastit tietokannasta
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT t.aika, r.koodi, r.lon, r.lat
            FROM tupa t, rastit r
            WHERE joukkue = %s
            AND r.id = t.rasti
            ORDER BY t.aika;"""
        cur.execute(sql,(joukkue["id"],))
        rastit = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()

    if form.is_submitted():
        #tarkistetaan onko joukkueen poisto vai muokkaus
        if form.poista.data == True:
            if len(rastit) > 1: # ei voida poistaa jos joukkueella rasteja
                flash("Joukkueella rasteja. Ei voida poistaa")
            else:
                try:
                    con = pool.get_connection()
                    cur = con.cursor(buffered=True, dictionary=True)
                    sql = """DELETE
                        FROM joukkueet
                        WHERE id = %s;"""
                    cur.execute(sql, (joukkue["id"],))
                    con.commit()
                except:
                    con.close()
                finally:
                    con.close()
                    session["joukkuenimi"] = None
                    return redirect(url_for("sarja", sarjanimi=session["sarjanimi"]))
        #validoidaan lomake muokattaessa
        elif form.validate():
            jnimi = form.nimi.data
            sarja = form.sarja.data-500
            salasana = form.salasana.data
            jasenet = [ v.strip() for k,v in form.data.items() if 'jasen' in k]
            while "" in jasenet:
                jasenet.remove("")
            jasenet = json.dumps(jasenet)
            #tarkistetaan onko salasana syötetty. Käytetään vanhaa jos ei ole
            if len(salasana) > 0:
                salasana = hash(joukkue["id"], salasana)
            else:
                salasana = joukkue["salasana"]
            #joukkueen tietojen muokkaus
            try:
                con = pool.get_connection()
                cur = con.cursor(buffered=True, dictionary=True)
                sql = """UPDATE joukkueet
                    SET joukkuenimi = %s,
                    sarja = %s,
                    salasana = %s,
                    jasenet = %s
                    WHERE id = %s;"""
                cur.execute(sql, (jnimi, sarja, salasana, jasenet, joukkue["id"]))
                con.commit()
            except:
                con.close()
            finally:
                con.close()
            #etsitään ja valitaan muokattu joukkue
            try:
                con = pool.get_connection()
                cur = con.cursor(buffered=True, dictionary=True)
                sql = """SELECT *
                    FROM joukkueet
                    WHERE id = %s;"""
                cur.execute(sql, (joukkue["id"],))
                tulos = cur.fetchone()
                session["joukkue"] = tulos
                session["joukkuenimi"] = jnimi
            except:
                con.close()
            finally:
                con.close()
            return redirect(url_for("sarja", sarjanimi=session["sarjanimi"]))

    return render_template("adminjoukkue.xhtml", form = form, rastit=rastit)

@app.route('/joukkueet/')
@app.route('/<sarjanimi>/joukkueet', methods = ["GET", "POST"])
@admin
def sarja(sarjanimi=None):
    if sarjanimi == None:
        return redirect(url_for("kilpailu", kilpailunimi=session["kisanimi"]))
    sarja = list(filter(lambda s : s["sarjanimi"] == sarjanimi, session["sarjat"]))[0]
    if len(sarja) < 1:
        return redirect(url_for("kilpailu", kilpailunimi=session["kisanimi"]))
    session["sarja"] = sarja
    session["sarjanimi"] = sarja["sarjanimi"]
    id = sarja["id"]
    #haetaan sarjan joukkueet
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT *
            FROM joukkueet j
            WHERE sarja IN
            (SELECT id
            FROM sarjat s
            WHERE id = %s)
            ORDER BY j.joukkuenimi;"""
        cur.execute(sql, (id,))
        rivit = cur.fetchall()
        session["joukkueet"] = rivit
    except:
        con.close()
    finally:
        con.close()

    form = Lomake()
    if form.validate_on_submit():
        jnimi = form.nimi.data
        jsalasana = form.salasana.data
        jasenet = [ v.strip() for k,v in form.data.items() if 'jasen' in k]
        while "" in jasenet:
            jasenet.remove("")
        jasenet = json.dumps(jasenet)
        #lisätään joukkue tietokantaan
        try:
            con = pool.get_connection()
            cur = con.cursor(buffered=True, dictionary=True)
            sql = """INSERT INTO joukkueet
                (joukkuenimi, sarja, jasenet)
                VALUES (%s, %s, %s);"""
            cur.execute(sql, (jnimi, id, jasenet))
            con.commit()
            id = cur.lastrowid
        except:
            con.close()
        #asetetaan salasana joukkueelle id:n perusteella
        finally:
            salasana = hash(id, jsalasana)
            sqlpw = """UPDATE joukkueet
            SET salasana = %s
            WHERE id =  %s;"""
            cur.execute(sqlpw, (salasana, id))
            con.commit()
            con.close()
        return redirect(url_for("sarja", sarjanimi=session["sarjanimi"]))

    return render_template("joukkueet.xhtml", joukkueet=rivit, form = form)

@app.route('/sarjat/')
@app.route('/<kilpailunimi>/sarjat', methods = ["GET"])
@admin
def kilpailu(kilpailunimi=None):
    if kilpailunimi == None:
         return redirect(url_for("index"))
    #Uunohdetaan aiemmin valitut sarjat ja joukkueet, jos valittu kilpailu on eri kuin aiemmin valittuna ollut.
    if kilpailunimi != session["kisanimi"]:
        session["sarja"] = None
        session["sarjanimi"] = None
        session["joukkue"] = None
        session["joukkuenimi"] = None
    #Etsitään oikea kilpailu
    kilpailu = list(filter(lambda k : k["kisanimi"] == kilpailunimi, session["kilpailut"]))[0]
    session["kilpailu"] = kilpailu
    session["kisanimi"] = kilpailu["kisanimi"]
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT *
            FROM sarjat s
            WHERE kilpailu IN
            (SELECT id
            FROM kilpailut k
            WHERE id = %s)
            ORDER BY s.kesto;"""
        cur.execute(sql, (kilpailu["id"],))
        sarjat = cur.fetchall()
        session["sarjat"] = sarjat
    except:
        con.close()
    finally:
        con.close()

    return render_template("sarjat.xhtml", sarjat=sarjat)

@app.route('/kilpailut', methods = ["GET"])
@admin
def index():
    #kaikkien kilpailujen hakeminen
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT *
            FROM kilpailut;"""
        cur.execute(sql,)
        kilpailut = cur.fetchall()
        session["kilpailut"] = kilpailut
    except:
        con.close()
    finally:
        con.close()

    return render_template("kilpailut.xhtml", kilpailut=kilpailut)

@app.route('/admin/', methods = ["GET","POST"])
def admin():
    class Login(PolyglotForm):
        username   = StringField(u"Tunnus")
        password = PasswordField(u'Salasana')
        submit = SubmitField(u"Kirjaudu sisään")
    form = Login()
    if (request.method == "POST"):
        uname = form.username.data
        psswrd = form.password.data
        try:
            con = pool.get_connection()
            cur = con.cursor(buffered=True, dictionary=True)
            sql = """SELECT *
                FROM users
                WHERE username = %s;"""
            cur.execute(sql, (uname,))
            tulos = cur.fetchone()
        except:
            con.close()
        finally:
            con.close()
        if (tulos):
            #tehdään salasanasta tiiviste, jonka jälkeen verrataan sitä tietokannassa olevaan salasanaan
            salasana = hash(psswrd, psswrd)
            if (uname.strip().upper() == tulos["username"].strip().upper() and salasana == tulos["password"]):
                session["admin"] = True
                session["kisanimi"] = None
                session["sarjanimi"] = None
                session["joukkuenimi"] = None
                return redirect(url_for("index"))
        flash("Kirjautuminen epäonnistui")
        return redirect(url_for("admin"))

    return render_template("adminlogin.xhtml", form = form)

@app.route('/muokkaa/<joukkuenimi>', methods=['GET', 'POST'])
@user
def muokkaa(joukkuenimi):
    joukkue = session["joukkue"]
    jasenet = json.loads(joukkue["jasenet"])
    #jos jäseniä ei ole 5 kpl, lisätään tyhjiä merkkijonoja
    for i in range(5):
        if (i >= len(jasenet)):
            jasenet.append("")
    #kaikkien sarjojen hakeminen tietokannasta
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT *
            FROM sarjat;"""
        cur.execute(sql,)
        rivit = cur.fetchall()
        session["sarjat"] = rivit
    except:
        con.close()
    finally:
        con.close()
    #lisätään sarjat alasvetolaatikkoa varten ja etsitään oletussarja
    sarjat = []
    for r in rivit:
        sarjat.append((r["id"]+500, r["sarjanimi"]))
    sarja = list(filter(lambda s: s[0] == joukkue["sarja"]+500, sarjat))[0]
    form = Lomake(data={
        "nimi": joukkuenimi,
        "jasen1":jasenet[0],
        "jasen2":jasenet[1],
        "jasen3":jasenet[2],
        "jasen4":jasenet[3],
        "jasen5":jasenet[4],
        }, sarja = sarja[0])
    form.sarja.choices = sarjat
    #haetaan joukkueen rastit tietokannasta
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT t.aika, r.koodi, r.lon, r.lat
            FROM tupa t, rastit r
            WHERE joukkue = %s
            AND r.id = t.rasti
            ORDER BY t.aika;"""
        cur.execute(sql,(joukkue["id"],))
        rastit = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()
    #lomakkeen validointi submit-tapahtuman jälkeen
    if form.validate_on_submit():
        jnimi = form.nimi.data
        salasana = form.salasana.data
        sarja = form.sarja.data-500
        #haetaan data jasen-alkuisista kentistä
        jasenet = [ v.strip() for k,v in form.data.items() if 'jasen' in k]
        #poistetaan jäsenlistasta tyhjät merkkijonot
        while "" in jasenet:
            jasenet.remove("")
        jasenet = json.dumps(jasenet)
        #luodaan salasana salasana jos on syötetty
        if len(salasana) > 0:
            salasana = hash(joukkue["id"], salasana)
        else:
            salasana = joukkue["salasana"]
        #joukkueen muokkaus
        try:
            con = pool.get_connection()
            cur = con.cursor(buffered=True, dictionary=True)
            sql = """UPDATE joukkueet
                SET joukkuenimi = %s,
                salasana = %s,
                sarja = %s,
                jasenet = %s
                WHERE id = %s;"""
            cur.execute(sql, (jnimi, salasana, sarja, jasenet, joukkue["id"]))
            con.commit()
        except:
            con.close()
        finally:
            con.close()
        #joukkueen hakeminen tietokannasta
        try:
            con = pool.get_connection()
            cur = con.cursor(buffered=True, dictionary=True)
            sql = """SELECT *
                FROM joukkueet
                WHERE id = %s;"""
            cur.execute(sql, (joukkue["id"],))
            tulos = cur.fetchone()
            session["joukkue"] = tulos
        except:
            con.close()
        finally:
            con.close()

    return render_template("joukkue.xhtml", form = form, rastit = rastit)


@app.route('/joukkuelistaus')
@user
def joukkuelistaus():
    # Etsitään kilpailun joukkueet
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT joukkueet.*, sarjat.*
            FROM sarjat, joukkueet, kilpailut
            WHERE joukkueet.sarja = sarjat.id
            AND sarjat.kilpailu = kilpailut.id
		    AND kilpailut.kisanimi = %s
		    ORDER BY sarjat.sarjanimi,
		    joukkueet.joukkuenimi;"""
        cur.execute(sql, (session["kilpailu"]["kisanimi"],))
        rivit = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()
    joukkueet = []
    for rivi in rivit:
        joukkue = {
            "joukkuenimi": rivi["joukkuenimi"],
            "sarjanimi": rivi["sarjanimi"],
            "jasenet": json.loads(rivi["jasenet"])
            }
        joukkue["jasenet"].sort()
        joukkueet.append(joukkue)
    results = []
    #ryhmitellään joukkueet sarjan mukaan
    for key, value in groupby(joukkueet, lambda x: x["sarjanimi"]):
        results.append( { "sarjanimi":key, "joukkueet": list(value) } )

    return render_template("listaus.xhtml", joukkueet = results)

@app.route('/login', methods = ["GET", "POST"])
def login():
    #kilpailujen etsiminen tietokannasta
    try:
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)
        sql = """SELECT *
            FROM kilpailut;"""
        cur.execute(sql,)
        rivit = cur.fetchall()
    except:
        con.close()
    finally:
        con.close()
    #lisätään kilpailut taulukkoon select-fieldiä varten
    kilpailut = []
    for rivi in rivit:
        kilpailut.append(rivi["kisanimi"])

    class Login(PolyglotForm):
        kisat   = SelectField(u"Kisa", choices=kilpailut)
        username = StringField(u'Joukkueen nimi')
        password = PasswordField(u'Salasana')
    form = Login()

    if (request.method == "POST"):
        kisa = form.kisat.data
        uname = form.username.data
        psswrd = form.password.data
        #Joukkueen etsiminen tietokannasta
        try:
            con = pool.get_connection()
            cur = con.cursor(buffered=True, dictionary=True)
            sql = """SELECT *
                FROM joukkueet
                WHERE joukkuenimi = %s;"""
            cur.execute(sql, (uname,))
            tulos = cur.fetchone()
            session["joukkue"] = tulos
        except:
            con.close()
        finally:
            con.close()

        if (tulos):
            salasana = hash(tulos["id"], psswrd)
            #Tarkistetaan että syötetty salasana täsmää tietokannassa olevan kanssa
            if (uname.strip().upper() == tulos["joukkuenimi"].strip().upper() and salasana == tulos["salasana"]):
                session["kirjautunut"] = "ok"
                kilpailu = list(filter(lambda k: k["kisanimi"] == kisa, rivit))[0]
                session["kilpailu"] = kilpailu
                return redirect(url_for("joukkuelistaus"))
        flash("Kirjautuminen epäonnistui")
        return redirect(url_for("login"))

    return render_template("userlogin.xhtml", form = form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

#luo salasanasta tiivisteen parametrien avulla
def hash(eka, toka):
    m = hashlib.sha512()
    m.update(str(eka).encode("UTF-8"))
    m.update(str(toka).encode("UTF-8"))
    return m.hexdigest()