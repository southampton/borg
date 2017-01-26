#!/usr/bin/python

from deskctl import app
from deskctl.lib.user import is_logged_in
from deskctl.lib.misc import deskctld_connect
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import grp
import pwd

################################################################################

@app.route('/')
def default():
	app.logger.debug("default()")

	return render_template('dashboard.html', title='dashboard')

@app.route('/software')
def software():
	## Connect to the desktop management service
	deskctld = deskctld_connect()

	## Get the current pkg task queue
	pkgStatus = deskctld.pkgStatus()

	if len(pkgStatus) == 0:
		pkgStatus = None
	
	return render_template('software.html',title='Software',active="software",pkgstatus=pkgStatus)

@app.route('/permissions/<group>',methods=['GET','POST'])
def permissions(group):
	if group not in ['users','vboxusers','sys','wheel']:
		abort(404)

	## Connect to the desktop management service
	deskctld = deskctld_connect()

	## Get current group members
	try:
		grp_object = grp.getgrnam(group)
	except KeyError as ex:
		raise app.FatalError("The group " + group + " does not exist on the system. Please contact ServiceLine for assistance")

	can_make_changes = False
	if is_logged_in():
		## load members of groups we need to check
		try:
			linuxsys = grp.getgrnam('linuxsys')
			linuxadm = grp.getgrnam('linuxadm')
			localsys = grp.getgrnam('sys')
		except KeyError as ex:
			raise app.FatalError("The group " + group + " does not exist on the system. Please contact ServiceLine for assistance")
		
		if session['username'] in linuxadm.gr_mem:
			## users in the linuxadm group have full perms whatever
			can_make_changes = True

		else:
			if group in ['users','vboxusers','sys']:
				## Only people in 'sys' or 'linuxsys'
				if session['username'] in linuxsys.gr_mem:
					can_make_changes = True
				elif session['username'] in localsys.gr_mem:
					can_make_changes = True

	## explanation text
	if group == "users":
		group_title = "SSH Access"
		group_desc  = "The users listed below can logon to this system remotely via SSH"
	elif group == "vboxusers":
		group_title = "VirtualBox Users"
		group_desc  = "The users listed below can create and run virtual machines within VirtualBox"
	elif group == "sys":
		group_title = "Administrators"
		group_desc  = "The users listed below are granted semi-administrator access, including software management, and detailed settings management. Most users, especially laptop users, should be listed here."
	elif group == "wheel":
		group_title = "Root Access"
		group_desc  = "The users listed below are granted FULL root access. Please use this sparingly. If a user is listed below iSolutions standard support ENDS!"

	if request.method == 'GET':
		group_members = []
		for member in grp_object.gr_mem:
	
			try:
				pwentry = pwd.getpwnam(member)
				gecos = pwentry.pw_gecos
			except KeyError as ex:
				gecos = "N/A (user no longer exists)"

			group_members.append({'username': member, 'gecos': gecos})

		return render_template('permissions.html',title='Permissions',active="permissions",activegrp=group,group_title=group_title,group_desc=group_desc,group_members=group_members,can_make_changes=can_make_changes)

	elif request.method == 'POST':
		if not can_make_changes:
			abort(403)

		if 'action' not in request.form:
			abort(400)

		if request.form['action'] == 'add':
			username = request.form['username']

			try:
				pwentry = pwd.getpwnam(username)
			except KeyError as ex:
				flash("The username you specified was not found","alert-danger")
				return redirect(url_for('permissions',group=group))

			## Try adding them to the group
			try:
				deskctld.groupAddUser(group,username)
			except Exception as ex:
				flash("Could not add username to group: " + str(ex),"alert-danger")
				return redirect(url_for('permissions',group=group))

			flash("Added '" + username + "' to " + group_title,"alert-success")
			return redirect(url_for('permissions',group=group))

		elif request.form['action'] == 'remove':
			username = request.form['username']

			if username not in grp_object.gr_mem:
				flash("Could not remove the username you specified because is not in the group","alert-danger")
				return redirect(url_for('permissions',group=group))
			else:

				try:
					deskctld.groupRemoveUser(group,username)
				except Exception as ex:
					flash("Could not remove username from group: " + str(ex),"alert-danger")
					return redirect(url_for('permissions',group=group))

				flash("Removed '" + username + "' from " + group_title,"alert-success")
				return redirect(url_for('permissions',group=group))