# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cstr, now_datetime, cint

from erpnext.controllers.status_updater import StatusUpdater


class TransactionBase(StatusUpdater):
	def load_notification_message(self):
		dt = self.doc.doctype.lower().replace(" ", "_")
		if int(frappe.conn.get_value("Notification Control", None, dt) or 0):
			self.doc.fields["__notification_message"] = \
				frappe.conn.get_value("Notification Control", None, dt + "_message")
							
	def validate_posting_time(self):
		if not self.doc.posting_time:
			self.doc.posting_time = now_datetime().strftime('%H:%M:%S')
			
	def add_calendar_event(self, opts, force=False):
		if self.doc.contact_by != cstr(self._prev.contact_by) or \
				self.doc.contact_date != cstr(self._prev.contact_date) or force:
			
			self.delete_events()
			self._add_calendar_event(opts)
			
	def delete_events(self):
		frappe.delete_doc("Event", frappe.conn.sql_list("""select name from `tabEvent` 
			where ref_type=%s and ref_name=%s""", (self.doc.doctype, self.doc.name)), 
			ignore_permissions=True)
			
	def _add_calendar_event(self, opts):
		opts = frappe._dict(opts)
		
		if self.doc.contact_date:
			event_doclist = [{
				"doctype": "Event",
				"owner": opts.owner or self.doc.owner,
				"subject": opts.subject,
				"description": opts.description,
				"starts_on": self.doc.contact_date + " 10:00:00",
				"event_type": "Private",
				"ref_type": self.doc.doctype,
				"ref_name": self.doc.name
			}]
			
			if frappe.conn.exists("Profile", self.doc.contact_by):
				event_doclist.append({
					"doctype": "Event User",
					"parentfield": "event_individuals",
					"person": self.doc.contact_by
				})
			
			frappe.bean(event_doclist).insert()
			
	def validate_uom_is_integer(self, uom_field, qty_fields):
		validate_uom_is_integer(self.doclist, uom_field, qty_fields)
			
	def validate_with_previous_doc(self, source_dt, ref):
		for key, val in ref.items():
			is_child = val.get("is_child_table")
			ref_doc = {}
			item_ref_dn = []
			for d in self.doclist.get({"doctype": source_dt}):
				ref_dn = d.fields.get(val["ref_dn_field"])
				if ref_dn:
					if is_child:
						self.compare_values({key: [ref_dn]}, val["compare_fields"], d)
						if ref_dn not in item_ref_dn:
							item_ref_dn.append(ref_dn)
						elif not val.get("allow_duplicate_prev_row_id"):
							frappe.msgprint(_("Row ") + cstr(d.idx + 1) + 
								_(": Duplicate row from same ") + key, raise_exception=1)
					elif ref_dn:
						ref_doc.setdefault(key, [])
						if ref_dn not in ref_doc[key]:
							ref_doc[key].append(ref_dn)
			if ref_doc:
				self.compare_values(ref_doc, val["compare_fields"])
	
	def compare_values(self, ref_doc, fields, doc=None):
		for ref_doctype, ref_dn_list in ref_doc.items():
			for ref_docname in ref_dn_list:
				prevdoc_values = frappe.conn.get_value(ref_doctype, ref_docname, 
					[d[0] for d in fields], as_dict=1)

				for field, condition in fields:
					if prevdoc_values[field] is not None:
						self.validate_value(field, condition, prevdoc_values[field], doc)
	
def delete_events(ref_type, ref_name):
	frappe.delete_doc("Event", frappe.conn.sql_list("""select name from `tabEvent` 
		where ref_type=%s and ref_name=%s""", (ref_type, ref_name)), for_reload=True)

class UOMMustBeIntegerError(frappe.ValidationError): pass

def validate_uom_is_integer(doclist, uom_field, qty_fields):
	if isinstance(qty_fields, basestring):
		qty_fields = [qty_fields]
	
	integer_uoms = filter(lambda uom: frappe.conn.get_value("UOM", uom, 
		"must_be_whole_number") or None, doclist.get_distinct_values(uom_field))
		
	if not integer_uoms:
		return

	for d in doclist:
		if d.fields.get(uom_field) in integer_uoms:
			for f in qty_fields:
				if d.fields.get(f):
					if cint(d.fields[f])!=d.fields[f]:
						frappe.msgprint(_("For UOM") + " '" + d.fields[uom_field] \
							+ "': " + _("Quantity cannot be a fraction.") \
							+ " " + _("In Row") + ": " + str(d.idx),
							raise_exception=UOMMustBeIntegerError)
