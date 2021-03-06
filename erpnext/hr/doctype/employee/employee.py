# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import getdate, validate_email_add, cstr, cint
from frappe.model.doc import make_autoname
from frappe import msgprint, throw, _
import frappe.permissions
from frappe.defaults import get_restrictions
from frappe.model.controller import DocListController

class DocType(DocListController):
	def autoname(self):
		naming_method = frappe.conn.get_value("HR Settings", None, "emp_created_by")
		if not naming_method:
			throw(_("Please setup Employee Naming System in Human Resource > HR Settings"))
		else:
			if naming_method=='Naming Series':
				self.doc.name = make_autoname(self.doc.naming_series + '.####')
			elif naming_method=='Employee Number':
				self.doc.name = self.doc.employee_number

		self.doc.employee = self.doc.name

	def validate(self):
		from erpnext.utilities import validate_status
		validate_status(self.doc.status, ["Active", "Left"])

		self.doc.employee = self.doc.name
		self.validate_date()
		self.validate_email()
		self.validate_status()
		self.validate_employee_leave_approver()

		if self.doc.user_id:
			self.validate_for_enabled_user_id()
			self.validate_duplicate_user_id()
		
	def on_update(self):
		if self.doc.user_id:
			self.restrict_user()
			self.update_user_default()
			self.update_profile()
		
		self.update_dob_event()
		self.restrict_leave_approver()
				
	def restrict_user(self):
		"""restrict to this employee for user"""
		self.add_restriction_if_required("Employee", self.doc.user_id)

	def update_user_default(self):
		frappe.conn.set_default("employee_name", self.doc.employee_name, self.doc.user_id)
		frappe.conn.set_default("company", self.doc.company, self.doc.user_id)
	
	def restrict_leave_approver(self):
		"""restrict to this employee for leave approver"""
		employee_leave_approvers = [d.leave_approver for d in self.doclist.get({"parentfield": "employee_leave_approvers"})]
		if self.doc.reports_to and self.doc.reports_to not in employee_leave_approvers:
			employee_leave_approvers.append(frappe.conn.get_value("Employee", self.doc.reports_to, "user_id"))
			
		for user in employee_leave_approvers:
			self.add_restriction_if_required("Employee", user)
			self.add_restriction_if_required("Leave Application", user)
				
	def add_restriction_if_required(self, doctype, user):
		if frappe.permissions.has_only_non_restrict_role(frappe.get_doctype(doctype), user) \
			and self.doc.name not in get_restrictions(user).get("Employee", []):
			
			frappe.defaults.add_default("Employee", self.doc.name, user, "Restriction")
	
	def update_profile(self):
		# add employee role if missing
		if not "Employee" in frappe.conn.sql_list("""select role from tabUserRole
				where parent=%s""", self.doc.user_id):
			from frappe.profile import add_role
			add_role(self.doc.user_id, "Employee")
			
		profile_wrapper = frappe.bean("Profile", self.doc.user_id)
		
		# copy details like Fullname, DOB and Image to Profile
		if self.doc.employee_name:
			employee_name = self.doc.employee_name.split(" ")
			if len(employee_name) >= 3:
				profile_wrapper.doc.last_name = " ".join(employee_name[2:])
				profile_wrapper.doc.middle_name = employee_name[1]
			elif len(employee_name) == 2:
				profile_wrapper.doc.last_name = employee_name[1]
			
			profile_wrapper.doc.first_name = employee_name[0]
				
		if self.doc.date_of_birth:
			profile_wrapper.doc.birth_date = self.doc.date_of_birth
		
		if self.doc.gender:
			profile_wrapper.doc.gender = self.doc.gender
			
		if self.doc.image:
			if not profile_wrapper.doc.user_image == self.doc.image:
				profile_wrapper.doc.user_image = self.doc.image
				try:
					frappe.doc({
						"doctype": "File Data",
						"file_name": self.doc.image,
						"attached_to_doctype": "Profile",
						"attached_to_name": self.doc.user_id
					}).insert()
				except frappe.DuplicateEntryError, e:
					# already exists
					pass
		profile_wrapper.ignore_permissions = True
		profile_wrapper.save()
		
	def validate_date(self):
		if self.doc.date_of_birth and self.doc.date_of_joining and getdate(self.doc.date_of_birth) >= getdate(self.doc.date_of_joining):
			throw(_("Date of Joining must be greater than Date of Birth"))

		elif self.doc.scheduled_confirmation_date and self.doc.date_of_joining and (getdate(self.doc.scheduled_confirmation_date) < getdate(self.doc.date_of_joining)):
			throw(_("Scheduled Confirmation Date must be greater than Date of Joining"))
		
		elif self.doc.final_confirmation_date and self.doc.date_of_joining and (getdate(self.doc.final_confirmation_date) < getdate(self.doc.date_of_joining)):
			throw(_("Final Confirmation Date must be greater than Date of Joining"))
		
		elif self.doc.date_of_retirement and self.doc.date_of_joining and (getdate(self.doc.date_of_retirement) <= getdate(self.doc.date_of_joining)):
			throw(_("Date Of Retirement must be greater than Date of Joining"))
		
		elif self.doc.relieving_date and self.doc.date_of_joining and (getdate(self.doc.relieving_date) <= getdate(self.doc.date_of_joining)):
			throw(_("Relieving Date must be greater than Date of Joining"))
		
		elif self.doc.contract_end_date and self.doc.date_of_joining and (getdate(self.doc.contract_end_date)<=getdate(self.doc.date_of_joining)):
			throw(_("Contract End Date must be greater than Date of Joining"))
	 
	def validate_email(self):
		if self.doc.company_email and not validate_email_add(self.doc.company_email):
			throw(_("Please enter valid Company Email"))
		if self.doc.personal_email and not validate_email_add(self.doc.personal_email):
			throw(_("Please enter valid Personal Email"))
				
	def validate_status(self):
		if self.doc.status == 'Left' and not self.doc.relieving_date:
			throw(_("Please enter relieving date."))

	def validate_for_enabled_user_id(self):
		enabled = frappe.conn.sql("""select name from `tabProfile` where 
			name=%s and enabled=1""", self.doc.user_id)
		if not enabled:
			throw("{id}: {user_id} {msg}".format(**{
				"id": _("User ID"),
				"user_id": self.doc.user_id,
				"msg": _("is disabled.")
			}))

	def validate_duplicate_user_id(self):
		employee = frappe.conn.sql_list("""select name from `tabEmployee` where 
			user_id=%s and status='Active' and name!=%s""", (self.doc.user_id, self.doc.name))
		if employee:
			throw("{id}: {user_id} {msg}: {employee}".format(**{
				"id": _("User ID"),
				"user_id": self.doc.user_id,
				"msg": _("is already assigned to Employee"),
				"employee": employee[0]
			}))
			
	def validate_employee_leave_approver(self):
		from frappe.profile import Profile
		from erpnext.hr.doctype.leave_application.leave_application import InvalidLeaveApproverError
		
		for l in self.doclist.get({"parentfield": "employee_leave_approvers"}):
			if "Leave Approver" not in Profile(l.leave_approver).get_roles():
				throw(_("Invalid Leave Approver") + ": \"" + l.leave_approver + "\"",
					exc=InvalidLeaveApproverError)

	def update_dob_event(self):
		if self.doc.status == "Active" and self.doc.date_of_birth \
			and not cint(frappe.conn.get_value("HR Settings", None, "stop_birthday_reminders")):
			birthday_event = frappe.conn.sql("""select name from `tabEvent` where repeat_on='Every Year' 
				and ref_type='Employee' and ref_name=%s""", self.doc.name)
			
			starts_on = self.doc.date_of_birth + " 00:00:00"
			ends_on = self.doc.date_of_birth + " 00:15:00"

			if birthday_event:
				event = frappe.bean("Event", birthday_event[0][0])
				event.doc.starts_on = starts_on
				event.doc.ends_on = ends_on
				event.save()
			else:
				frappe.bean({
					"doctype": "Event",
					"subject": _("Birthday") + ": " + self.doc.employee_name,
					"description": _("Happy Birthday!") + " " + self.doc.employee_name,
					"starts_on": starts_on,
					"ends_on": ends_on,
					"event_type": "Public",
					"all_day": 1,
					"send_reminder": 1,
					"repeat_this_event": 1,
					"repeat_on": "Every Year",
					"ref_type": "Employee",
					"ref_name": self.doc.name
				}).insert()
		else:
			frappe.conn.sql("""delete from `tabEvent` where repeat_on='Every Year' and
				ref_type='Employee' and ref_name=%s""", self.doc.name)

@frappe.whitelist()
def get_retirement_date(date_of_birth=None):
	import datetime
	ret = {}
	if date_of_birth:
		dt = getdate(date_of_birth) + datetime.timedelta(21915)
		ret = {'date_of_retirement': dt.strftime('%Y-%m-%d')}
	return ret