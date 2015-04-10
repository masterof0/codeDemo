#!/usr/bin/python

import sqlite3, boto.ec2, os
from flask import Flask, g, render_template, request, url_for, redirect, flash
from flask_bootstrap import Bootstrap
from wtforms import StringField, SelectField, IntegerField, validators
from flask_wtf import Form 
from modules import aws

app = Flask(__name__)
app.secret_key = '\xc8`\x1dB\xb9~\xb4w|\xafd\xc9%\xc9\x05\xe5!&\x062\x81h\x81\xb8'
Bootstrap(app)

class reservation(Form):
  num = IntegerField('num', [validators.Required(), validators.NumberRange(min=1, max=10)])
  iType = SelectField('iType', choices=[('t2.micro', 'T2 Micro (preferred)'), ('t2.medium', 'T2 Medium'), ('m3.xlarge', 'M3 X-Large (training)')])
  name = StringField('name', [validators.Required()])

@app.before_request
def before_request():
  g.db = aws.awsDB()

@app.teardown_request
def teardown_request(exception):
  db = getattr(g, 'db', None)
  if db is not None:
    db.close()

@app.route('/')
def index():
  return redirect('instances', code=302)

@app.route('/instances', methods=['GET', 'POST'])
def instances():
  if request.method == "POST":
    action = request.form['action']
    resType = request.form['resType']
    resValue = request.form['resValue']
    if action == 'update':
      if resType == 'instance_id':
        instances = aws.connect('','').get_only_instances(instance_ids=[resValue])
        for i in instances: 
          passwd = aws.getPass('','', i, aws.awsDir())
          g.db.execute("update instances set public_ip=?, password=?, state=? where instance_id=?;", (i.ip_address, passwd, str(i._state), i.id))
      g.db.commit()
      flash('Instance ' + resValue + ' has been successfully updated')
    if action == 'terminate':
      aws.connect('','').terminate_instances([resValue])
      g.db.execute("delete from instances where instance_id='%s';" % resValue)
      g.db.commit()
      flash('Instance ' + resValue + ' has been successfully terminated')
    return redirect('instances', code=302)
  if request.method == "GET":
    cur = g.db.execute('select * from instances;')
    instances = [dict(hostname=row[2], instance_id=row[0], reservation_id=row[1], public_ip=row[3], password=row[4], state=row[5]) for row in cur.fetchall()]
    return render_template('instances.html', entries=instances, pageTitle="AWS Instances")

@app.route('/reservation', methods=['GET', 'POST'])
def makeReservation():
  form = reservation()
  admin = 'cjohnson'
  if request.method == "GET":
    return render_template('reservation.html', form=form, pageTitle="AWS Reservation")
  if request.method == "POST":
    #Check for existing keys and create if needed
    if aws.connect('','').get_key_pair(form.name.data):
      if not os.path.exists(aws.awsDir() + form.name.data + '.pem'): 
        return ("This name is already taken. Please try again with new name")
    else:
      key = aws.connect('','').create_key_pair(form.name.data)
      key.save(aws.awsDir())
    #Create reservations
    res = aws.connect('','').run_instances('ami-ff21c0bb',max_count=form.num.data, key_name=form.name.data, security_groups=['sg_training'], instance_type=form.iType.data)
    flash("Your reservation id for this defensics request is: " + str(res.id))
    flash("Please note it may take up to 30 minutes for the images to launch and be fully available")
    instances = res.instances
    #Create tabale if needed
    cur = g.db.execute('select name from sqlite_master where type="table" and name="instances";')
    if not cur.fetchone():
      g.db.execute("create table instances(instance_id, reservation_id, name, public_ip, password, state, key);")
    #Write instance information to database and add appropriate tags
    for index, i in enumerate(instances):
      commonName = form.name.data + ':' + str(index) + '_' + res.id
      g.db.execute("insert into instances values (?,?,?,?,null,?,?)", (i.id, res.id, commonName, i.ip_address, str(i._state), form.name.data))
      i.add_tag('Name',value=commonName)
      i.add_tag('Admin',value=admin)
      i.add_tag('Status',value='training')
    g.db.commit()
    return redirect('instances', code=302)


#@app.route('/update', methods=['GET','POST'])
#def update():
#  form = updateForm()#csrf_enabled=False)
#  if request.method == "GET":
#    return render_template('update.html', form=form)
#  if request.method == "POST":
#    if form.type.data == 'res_id':
#      g.db.execute("delete from instances where reservation_id='%s';" % form.value.data)
#      reservations = aws.connect('','').get_all_reservations()
#      for r in reservations:
#        if r.id == form.value.data:
#          instances = r.instances
#          for i in instances:
#            passwd = aws.getPass('','', i, aws.awsDir())
#            g.db.execute("insert into instances values (?,?,?,?,?,?)", (i.id, form.value.data, i.tags['Name'], i.ip_address, passwd, str(i._state)))  
#      g.db.commit()
#      flash('Reservation ' + form.value.data + ' has been successfully updated')
#      return redirect('instances', code=302)
#    if form.type.data == 'instance_id':
#      instances = aws.connect('','').get_only_instances()
#      for i in instances:
#        if i.id == form.value.data:
#          passwd = aws.getPass('','', i, aws.awsDir())
#          g.db.execute("update instances set public_ip=?, password=?, state=? where instance_id=?;", (i.ip_address, passwd, str(i._state), i.id))
#      g.db.commit()
#      flash('Instance ' + form.value.data + ' has been successfully updated')
#      return redirect('instances', code=302)
#    if form.type.data == 'admin':
#      instances = aws.connect('','').get_only_instances()
#      for i in instances:
#        if i.tags['Admin'] == form.value.data:
#          passwd = aws.getPass('','', i, aws.awsDir())
#          g.db.execute("update instances set public_ip=?, password=?, state=? where instance_id=?;", (i.ip_address, passwd, str(i._state), i.id))
#      g.db.commit()
#      flash('Machines for ' + form.value.data + ' have been successfully updated')
#      return redirect('instances', code=302)

@app.errorhandler(404)
def page_not_found(error):
    return 'This page does not exist', 404

if __name__ == '__main__':
  app.run(host='0.0.0.0',debug=True)

