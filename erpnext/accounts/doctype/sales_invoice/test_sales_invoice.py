# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
import unittest, json
from frappe.utils import flt
from frappe.model.bean import DocstatusTransitionError, TimestampMismatchError
from erpnext.accounts.utils import get_stock_and_account_difference
from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import set_perpetual_inventory

class TestSalesInvoice(unittest.TestCase):
	def make(self):
		w = frappe.bean(copy=test_records[0])
		w.doc.is_pos = 0
		w.insert()
		w.submit()
		return w
		
	def test_double_submission(self):
		w = frappe.bean(copy=test_records[0])
		w.doc.docstatus = '0'
		w.insert()
		
		w2 = [d for d in w.doclist]
		w.submit()
		
		w = frappe.bean(w2)
		self.assertRaises(DocstatusTransitionError, w.submit)
		
	def test_timestamp_change(self):
		w = frappe.bean(copy=test_records[0])
		w.doc.docstatus = '0'
		w.insert()

		w2 = frappe.bean([d.fields.copy() for d in w.doclist])
		
		import time
		time.sleep(1)
		w.save()
		
		import time
		time.sleep(1)
		self.assertRaises(TimestampMismatchError, w2.save)
		
	def test_sales_invoice_calculation_base_currency(self):
		si = frappe.bean(copy=test_records[2])
		si.insert()
		
		expected_values = {
			"keys": ["price_list_rate", "discount_percentage", "rate", "amount", 
				"base_price_list_rate", "base_rate", "base_amount"],
			"_Test Item Home Desktop 100": [50, 0, 50, 500, 50, 50, 500],
			"_Test Item Home Desktop 200": [150, 0, 150, 750, 150, 150, 750],
		}
		
		# check if children are saved
		self.assertEquals(len(si.doclist.get({"parentfield": "entries"})),
			len(expected_values)-1)
		
		# check if item values are calculated
		for d in si.doclist.get({"parentfield": "entries"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.item_code][i])
		
		# check net total
		self.assertEquals(si.doc.net_total, 1250)
		self.assertEquals(si.doc.net_total_export, 1250)
		
		# check tax calculation
		expected_values = {
			"keys": ["tax_amount", "total"],
			"_Test Account Shipping Charges - _TC": [100, 1350],
			"_Test Account Customs Duty - _TC": [125, 1475],
			"_Test Account Excise Duty - _TC": [140, 1615],
			"_Test Account Education Cess - _TC": [2.8, 1617.8],
			"_Test Account S&H Education Cess - _TC": [1.4, 1619.2],
			"_Test Account CST - _TC": [32.38, 1651.58],
			"_Test Account VAT - _TC": [156.25, 1807.83],
			"_Test Account Discount - _TC": [-180.78, 1627.05]
		}
		
		for d in si.doclist.get({"parentfield": "other_charges"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.account_head][i])
				
		self.assertEquals(si.doc.grand_total, 1627.05)
		self.assertEquals(si.doc.grand_total_export, 1627.05)
		
	def test_sales_invoice_calculation_export_currency(self):
		si = frappe.bean(copy=test_records[2])
		si.doc.currency = "USD"
		si.doc.conversion_rate = 50
		si.doclist[1].rate = 1
		si.doclist[1].price_list_rate = 1
		si.doclist[2].rate = 3
		si.doclist[2].price_list_rate = 3
		si.insert()
		
		expected_values = {
			"keys": ["price_list_rate", "discount_percentage", "rate", "amount", 
				"base_price_list_rate", "base_rate", "base_amount"],
			"_Test Item Home Desktop 100": [1, 0, 1, 10, 50, 50, 500],
			"_Test Item Home Desktop 200": [3, 0, 3, 15, 150, 150, 750],
		}
		
		# check if children are saved
		self.assertEquals(len(si.doclist.get({"parentfield": "entries"})),
			len(expected_values)-1)
		
		# check if item values are calculated
		for d in si.doclist.get({"parentfield": "entries"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.item_code][i])
		
		# check net total
		self.assertEquals(si.doc.net_total, 1250)
		self.assertEquals(si.doc.net_total_export, 25)
		
		# check tax calculation
		expected_values = {
			"keys": ["tax_amount", "total"],
			"_Test Account Shipping Charges - _TC": [100, 1350],
			"_Test Account Customs Duty - _TC": [125, 1475],
			"_Test Account Excise Duty - _TC": [140, 1615],
			"_Test Account Education Cess - _TC": [2.8, 1617.8],
			"_Test Account S&H Education Cess - _TC": [1.4, 1619.2],
			"_Test Account CST - _TC": [32.38, 1651.58],
			"_Test Account VAT - _TC": [156.25, 1807.83],
			"_Test Account Discount - _TC": [-180.78, 1627.05]
		}
		
		for d in si.doclist.get({"parentfield": "other_charges"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.account_head][i])
				
		self.assertEquals(si.doc.grand_total, 1627.05)
		self.assertEquals(si.doc.grand_total_export, 32.54)

	def test_sales_invoice_discount_amount(self):
		si = frappe.bean(copy=test_records[3])
		si.doc.discount_amount = 104.95
		si.doclist.append({
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Amount",
			"account_head": "_Test Account Service Tax - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Service Tax",
			"rate": 10,
			"row_id": 8,
			"idx": 9
		})
		si.insert()
		
		expected_values = {
			"keys": ["price_list_rate", "discount_percentage", "rate", "amount", 
				"base_price_list_rate", "base_rate", "base_amount"],
			"_Test Item Home Desktop 100": [62.5, 0, 62.5, 625.0, 50, 50, 465.37],
			"_Test Item Home Desktop 200": [190.66, 0, 190.66, 953.3, 150, 150, 698.08],
		}
		
		# check if children are saved
		self.assertEquals(len(si.doclist.get({"parentfield": "entries"})),
			len(expected_values)-1)
		
		# check if item values are calculated
		for d in si.doclist.get({"parentfield": "entries"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.item_code][i])
		
		# check net total
		self.assertEquals(si.doc.net_total, 1163.45)
		self.assertEquals(si.doc.net_total_export, 1578.3)
		
		# check tax calculation
		expected_values = {
			"keys": ["tax_amount", "tax_amount_after_discount_amount", "total"],
			"_Test Account Excise Duty - _TC": [140, 130.31, 1293.76],
			"_Test Account Education Cess - _TC": [2.8, 2.61, 1296.37],
			"_Test Account S&H Education Cess - _TC": [1.4, 1.31, 1297.68],
			"_Test Account CST - _TC": [27.88, 25.96, 1323.64],
			"_Test Account VAT - _TC": [156.25, 145.43, 1469.07],
			"_Test Account Customs Duty - _TC": [125, 116.35, 1585.42],
			"_Test Account Shipping Charges - _TC": [100, 100, 1685.42],
			"_Test Account Discount - _TC": [-180.33, -168.54, 1516.88],
			"_Test Account Service Tax - _TC": [-18.03, -16.88, 1500]
		}
		
		for d in si.doclist.get({"parentfield": "other_charges"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.account_head][i])
				
		self.assertEquals(si.doc.grand_total, 1500)
		self.assertEquals(si.doc.grand_total_export, 1500)

	def test_discount_amount_gl_entry(self):
		si = frappe.bean(copy=test_records[3])
		si.doc.discount_amount = 104.95
		si.doclist.append({
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Amount",
			"account_head": "_Test Account Service Tax - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Service Tax",
			"rate": 10,
			"row_id": 8,
			"idx": 9
		})
		si.insert()
		si.submit()

		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)

		self.assertTrue(gl_entries)

		expected_values = sorted([
			[si.doc.debit_to, 1500, 0.0],
			[test_records[3][1]["income_account"], 0.0, 1163.45],
			[test_records[3][3]["account_head"], 0.0, 130.31],
			[test_records[3][4]["account_head"], 0.0, 2.61],
			[test_records[3][5]["account_head"], 0.0, 1.31],
			[test_records[3][6]["account_head"], 0.0, 25.96],
			[test_records[3][7]["account_head"], 0.0, 145.43],
			[test_records[3][8]["account_head"], 0.0, 116.35],
			[test_records[3][9]["account_head"], 0.0, 100],
			[test_records[3][10]["account_head"], 168.54, 0.0],
			["_Test Account Service Tax - _TC", 16.88, 0.0],
		])

		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)

		# cancel
		si.cancel()

		gle = frappe.conn.sql("""select * from `tabGL Entry` 
			where voucher_type='Sales Invoice' and voucher_no=%s""", si.doc.name)

		self.assertFalse(gle)

	def test_inclusive_rate_validations(self):
		si = frappe.bean(copy=test_records[2])
		for i, tax in enumerate(si.doclist.get({"parentfield": "other_charges"})):
			tax.idx = i+1
		
		si.doclist[1].price_list_rate = 62.5
		si.doclist[1].price_list_rate = 191
		for i in [3, 5, 6, 7, 8, 9]:
			si.doclist[i].included_in_print_rate = 1
		
		# tax type "Actual" cannot be inclusive
		self.assertRaises(frappe.ValidationError, si.insert)
		
		# taxes above included type 'On Previous Row Total' should also be included
		si.doclist[3].included_in_print_rate = 0
		self.assertRaises(frappe.ValidationError, si.insert)
		
	def test_sales_invoice_calculation_base_currency_with_tax_inclusive_price(self):
		# prepare
		si = frappe.bean(copy=test_records[3])
		si.insert()
		
		expected_values = {
			"keys": ["price_list_rate", "discount_percentage", "rate", "amount", 
				"base_price_list_rate", "base_rate", "base_amount"],
			"_Test Item Home Desktop 100": [62.5, 0, 62.5, 625.0, 50, 50, 499.98],
			"_Test Item Home Desktop 200": [190.66, 0, 190.66, 953.3, 150, 150, 750],
		}
		
		# check if children are saved
		self.assertEquals(len(si.doclist.get({"parentfield": "entries"})),
			len(expected_values)-1)
		
		# check if item values are calculated
		for d in si.doclist.get({"parentfield": "entries"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.item_code][i])
		
		# check net total
		self.assertEquals(si.doc.net_total, 1249.98)
		self.assertEquals(si.doc.net_total_export, 1578.3)
		
		# check tax calculation
		expected_values = {
			"keys": ["tax_amount", "total"],
			"_Test Account Excise Duty - _TC": [140, 1389.98],
			"_Test Account Education Cess - _TC": [2.8, 1392.78],
			"_Test Account S&H Education Cess - _TC": [1.4, 1394.18],
			"_Test Account CST - _TC": [27.88, 1422.06],
			"_Test Account VAT - _TC": [156.25, 1578.31],
			"_Test Account Customs Duty - _TC": [125, 1703.31],
			"_Test Account Shipping Charges - _TC": [100, 1803.31],
			"_Test Account Discount - _TC": [-180.33, 1622.98]
		}
		
		for d in si.doclist.get({"parentfield": "other_charges"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.account_head][i])
		
		self.assertEquals(si.doc.grand_total, 1622.98)
		self.assertEquals(si.doc.grand_total_export, 1622.98)
		
	def test_sales_invoice_calculation_export_currency_with_tax_inclusive_price(self):
		# prepare
		si = frappe.bean(copy=test_records[3])
		si.doc.currency = "USD"
		si.doc.conversion_rate = 50
		si.doclist[1].price_list_rate = 55.56
		si.doclist[1].discount_percentage = 10
		si.doclist[2].price_list_rate = 187.5
		si.doclist[2].discount_percentage = 20
		si.doclist[9].rate = 5000
		
		si.insert()
		
		expected_values = {
			"keys": ["price_list_rate", "discount_percentage", "rate", "amount", 
				"base_price_list_rate", "base_rate", "base_amount"],
			"_Test Item Home Desktop 100": [55.56, 10, 50, 500, 2222.11, 1999.9, 19999.04],
			"_Test Item Home Desktop 200": [187.5, 20, 150, 750, 7375.66, 5900.53, 29502.66],
		}
		
		# check if children are saved
		self.assertEquals(len(si.doclist.get({"parentfield": "entries"})),
			len(expected_values)-1)
		
		# check if item values are calculated
		for d in si.doclist.get({"parentfield": "entries"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.item_code][i])
		
		# check net total
		self.assertEquals(si.doc.net_total, 49501.7)
		self.assertEquals(si.doc.net_total_export, 1250)
		
		# check tax calculation
		expected_values = {
			"keys": ["tax_amount", "total"],
			"_Test Account Excise Duty - _TC": [5540.22, 55041.92],
			"_Test Account Education Cess - _TC": [110.81, 55152.73],
			"_Test Account S&H Education Cess - _TC": [55.4, 55208.13],
			"_Test Account CST - _TC": [1104.16, 56312.29],
			"_Test Account VAT - _TC": [6187.71, 62500],
			"_Test Account Customs Duty - _TC": [4950.17, 67450.17],
			"_Test Account Shipping Charges - _TC": [5000, 72450.17],
			"_Test Account Discount - _TC": [-7245.01, 65205.16]
		}
		
		for d in si.doclist.get({"parentfield": "other_charges"}):
			for i, k in enumerate(expected_values["keys"]):
				self.assertEquals(d.fields.get(k), expected_values[d.account_head][i])
		
		self.assertEquals(si.doc.grand_total, 65205.16)
		self.assertEquals(si.doc.grand_total_export, 1304.1)

	def test_outstanding(self):
		w = self.make()
		self.assertEquals(w.doc.outstanding_amount, w.doc.grand_total)
		
	def test_payment(self):
		frappe.conn.sql("""delete from `tabGL Entry`""")
		w = self.make()
		
		from erpnext.accounts.doctype.journal_voucher.test_journal_voucher \
			import test_records as jv_test_records
			
		jv = frappe.bean(frappe.copy_doclist(jv_test_records[0]))
		jv.doclist[1].against_invoice = w.doc.name
		jv.insert()
		jv.submit()
		
		self.assertEquals(frappe.conn.get_value("Sales Invoice", w.doc.name, "outstanding_amount"),
			161.8)
	
		jv.cancel()
		self.assertEquals(frappe.conn.get_value("Sales Invoice", w.doc.name, "outstanding_amount"),
			561.8)
			
	def test_time_log_batch(self):
		tlb = frappe.bean("Time Log Batch", "_T-Time Log Batch-00001")
		tlb.submit()
		
		si = frappe.bean(frappe.copy_doclist(test_records[0]))
		si.doclist[1].time_log_batch = "_T-Time Log Batch-00001"
		si.insert()
		si.submit()
		
		self.assertEquals(frappe.conn.get_value("Time Log Batch", "_T-Time Log Batch-00001",
		 	"status"), "Billed")

		self.assertEquals(frappe.conn.get_value("Time Log", "_T-Time Log-00001", "status"), 
			"Billed")

		si.cancel()

		self.assertEquals(frappe.conn.get_value("Time Log Batch", "_T-Time Log Batch-00001", 
			"status"), "Submitted")

		self.assertEquals(frappe.conn.get_value("Time Log", "_T-Time Log-00001", "status"), 
			"Batched for Billing")
			
	def test_sales_invoice_gl_entry_without_aii(self):
		self.clear_stock_account_balance()
		set_perpetual_inventory(0)
		si = frappe.bean(copy=test_records[1])
		si.insert()
		si.submit()
		
		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
		])
		
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
			
		# cancel
		si.cancel()
		
		gle = frappe.conn.sql("""select * from `tabGL Entry` 
			where voucher_type='Sales Invoice' and voucher_no=%s""", si.doc.name)
		
		self.assertFalse(gle)
		
	def test_pos_gl_entry_with_aii(self):
		self.clear_stock_account_balance()
		set_perpetual_inventory()
		
		self._insert_purchase_receipt()
		self._insert_pos_settings()
		
		pos = frappe.copy_doclist(test_records[1])
		pos[0]["is_pos"] = 1
		pos[0]["update_stock"] = 1
		pos[0]["posting_time"] = "12:05"
		pos[0]["cash_bank_account"] = "_Test Account Bank Account - _TC"
		pos[0]["paid_amount"] = 600.0

		si = frappe.bean(copy=pos)
		si.insert()
		si.submit()
		
		# check stock ledger entries
		sle = frappe.conn.sql("""select * from `tabStock Ledger Entry` 
			where voucher_type = 'Sales Invoice' and voucher_no = %s""", 
			si.doc.name, as_dict=1)[0]
		self.assertTrue(sle)
		self.assertEquals([sle.item_code, sle.warehouse, sle.actual_qty], 
			["_Test Item", "_Test Warehouse - _TC", -1.0])
		
		# check gl entries
		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc, debit asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		stock_in_hand = frappe.conn.get_value("Account", {"master_name": "_Test Warehouse - _TC"})
				
		expected_gl_entries = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[pos[1]["income_account"], 0.0, 500.0],
			[pos[2]["account_head"], 0.0, 80.0],
			[pos[3]["account_head"], 0.0, 50.0],
			[stock_in_hand, 0.0, 75.0],
			[pos[1]["expense_account"], 75.0, 0.0],
			[si.doc.debit_to, 0.0, 600.0],
			["_Test Account Bank Account - _TC", 600.0, 0.0]
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_gl_entries[i][0], gle.account)
			self.assertEquals(expected_gl_entries[i][1], gle.debit)
			self.assertEquals(expected_gl_entries[i][2], gle.credit)
		
		si.cancel()
		gle = frappe.conn.sql("""select * from `tabGL Entry` 
			where voucher_type='Sales Invoice' and voucher_no=%s""", si.doc.name)
		
		self.assertFalse(gle)
		
		self.assertFalse(get_stock_and_account_difference([stock_in_hand]))
		
		set_perpetual_inventory(0)
		
	def test_si_gl_entry_with_aii_and_update_stock_with_warehouse_but_no_account(self):
		self.clear_stock_account_balance()
		set_perpetual_inventory()
		frappe.delete_doc("Account", "_Test Warehouse No Account - _TC")
		
		# insert purchase receipt
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import test_records \
			as pr_test_records
		pr = frappe.bean(copy=pr_test_records[0])
		pr.doc.naming_series = "_T-Purchase Receipt-"
		pr.doclist[1].warehouse = "_Test Warehouse No Account - _TC"
		pr.insert()
		pr.submit()
		
		si_doclist = frappe.copy_doclist(test_records[1])
		si_doclist[0]["update_stock"] = 1
		si_doclist[0]["posting_time"] = "12:05"
		si_doclist[1]["warehouse"] = "_Test Warehouse No Account - _TC"

		si = frappe.bean(copy=si_doclist)
		si.insert()
		si.submit()
		
		# check stock ledger entries
		sle = frappe.conn.sql("""select * from `tabStock Ledger Entry` 
			where voucher_type = 'Sales Invoice' and voucher_no = %s""", 
			si.doc.name, as_dict=1)[0]
		self.assertTrue(sle)
		self.assertEquals([sle.item_code, sle.warehouse, sle.actual_qty], 
			["_Test Item", "_Test Warehouse No Account - _TC", -1.0])
		
		# check gl entries
		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc, debit asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_gl_entries = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[si_doclist[1]["income_account"], 0.0, 500.0],
			[si_doclist[2]["account_head"], 0.0, 80.0],
			[si_doclist[3]["account_head"], 0.0, 50.0],
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_gl_entries[i][0], gle.account)
			self.assertEquals(expected_gl_entries[i][1], gle.debit)
			self.assertEquals(expected_gl_entries[i][2], gle.credit)
				
		si.cancel()
		gle = frappe.conn.sql("""select * from `tabGL Entry` 
			where voucher_type='Sales Invoice' and voucher_no=%s""", si.doc.name)
		
		self.assertFalse(gle)
		set_perpetual_inventory(0)
		
	def test_sales_invoice_gl_entry_with_aii_no_item_code(self):
		self.clear_stock_account_balance()
		set_perpetual_inventory()
				
		si_copy = frappe.copy_doclist(test_records[1])
		si_copy[1]["item_code"] = None
		si = frappe.bean(si_copy)		
		si.insert()
		si.submit()
		
		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
		
		set_perpetual_inventory(0)
	
	def test_sales_invoice_gl_entry_with_aii_non_stock_item(self):
		self.clear_stock_account_balance()
		set_perpetual_inventory()
		si_copy = frappe.copy_doclist(test_records[1])
		si_copy[1]["item_code"] = "_Test Non Stock Item"
		si = frappe.bean(si_copy)
		si.insert()
		si.submit()
		
		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
				
		set_perpetual_inventory(0)
		
	def _insert_purchase_receipt(self):
		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import test_records \
			as pr_test_records
		pr = frappe.bean(copy=pr_test_records[0])
		pr.doc.naming_series = "_T-Purchase Receipt-"
		pr.insert()
		pr.submit()
		
	def _insert_delivery_note(self):
		from erpnext.stock.doctype.delivery_note.test_delivery_note import test_records \
			as dn_test_records
		dn = frappe.bean(copy=dn_test_records[0])
		dn.doc.naming_series = "_T-Delivery Note-"
		dn.insert()
		dn.submit()
		return dn
		
	def _insert_pos_settings(self):
		from erpnext.accounts.doctype.pos_setting.test_pos_setting \
			import test_records as pos_setting_test_records
		frappe.conn.sql("""delete from `tabPOS Setting`""")
		
		ps = frappe.bean(copy=pos_setting_test_records[0])
		ps.insert()
		
	def test_sales_invoice_with_advance(self):
		from erpnext.accounts.doctype.journal_voucher.test_journal_voucher \
			import test_records as jv_test_records
			
		jv = frappe.bean(copy=jv_test_records[0])
		jv.insert()
		jv.submit()
		
		si = frappe.bean(copy=test_records[0])
		si.doclist.append({
			"doctype": "Sales Invoice Advance",
			"parentfield": "advance_adjustment_details",
			"journal_voucher": jv.doc.name,
			"jv_detail_no": jv.doclist[1].name,
			"advance_amount": 400,
			"allocated_amount": 300,
			"remarks": jv.doc.remark
		})
		si.insert()
		si.submit()
		si.load_from_db()
		
		self.assertTrue(frappe.conn.sql("""select name from `tabJournal Voucher Detail`
			where against_invoice=%s""", si.doc.name))
		
		self.assertTrue(frappe.conn.sql("""select name from `tabJournal Voucher Detail`
			where against_invoice=%s and credit=300""", si.doc.name))
			
		self.assertEqual(si.doc.outstanding_amount, 261.8)
		
		si.cancel()
		
		self.assertTrue(not frappe.conn.sql("""select name from `tabJournal Voucher Detail`
			where against_invoice=%s""", si.doc.name))
			
	def test_recurring_invoice(self):
		from frappe.utils import get_first_day, get_last_day, add_to_date, nowdate, getdate
		from erpnext.accounts.utils import get_fiscal_year
		today = nowdate()
		base_si = frappe.bean(copy=test_records[0])
		base_si.doc.fields.update({
			"convert_into_recurring_invoice": 1,
			"recurring_type": "Monthly",
			"notification_email_address": "test@example.com, test1@example.com, test2@example.com",
			"repeat_on_day_of_month": getdate(today).day,
			"posting_date": today,
			"fiscal_year": get_fiscal_year(today)[0],
			"invoice_period_from_date": get_first_day(today),
			"invoice_period_to_date": get_last_day(today)
		})
		
		# monthly
		si1 = frappe.bean(copy=base_si.doclist)
		si1.insert()
		si1.submit()
		self._test_recurring_invoice(si1, True)
		
		# monthly without a first and last day period
		si2 = frappe.bean(copy=base_si.doclist)
		si2.doc.fields.update({
			"invoice_period_from_date": today,
			"invoice_period_to_date": add_to_date(today, days=30)
		})
		si2.insert()
		si2.submit()
		self._test_recurring_invoice(si2, False)
		
		# quarterly
		si3 = frappe.bean(copy=base_si.doclist)
		si3.doc.fields.update({
			"recurring_type": "Quarterly",
			"invoice_period_from_date": get_first_day(today),
			"invoice_period_to_date": get_last_day(add_to_date(today, months=3))
		})
		si3.insert()
		si3.submit()
		self._test_recurring_invoice(si3, True)
		
		# quarterly without a first and last day period
		si4 = frappe.bean(copy=base_si.doclist)
		si4.doc.fields.update({
			"recurring_type": "Quarterly",
			"invoice_period_from_date": today,
			"invoice_period_to_date": add_to_date(today, months=3)
		})
		si4.insert()
		si4.submit()
		self._test_recurring_invoice(si4, False)
		
		# yearly
		si5 = frappe.bean(copy=base_si.doclist)
		si5.doc.fields.update({
			"recurring_type": "Yearly",
			"invoice_period_from_date": get_first_day(today),
			"invoice_period_to_date": get_last_day(add_to_date(today, years=1))
		})
		si5.insert()
		si5.submit()
		self._test_recurring_invoice(si5, True)
		
		# yearly without a first and last day period
		si6 = frappe.bean(copy=base_si.doclist)
		si6.doc.fields.update({
			"recurring_type": "Yearly",
			"invoice_period_from_date": today,
			"invoice_period_to_date": add_to_date(today, years=1)
		})
		si6.insert()
		si6.submit()
		self._test_recurring_invoice(si6, False)
		
		# change posting date but keep recuring day to be today
		si7 = frappe.bean(copy=base_si.doclist)
		si7.doc.fields.update({
			"posting_date": add_to_date(today, days=-1)
		})
		si7.insert()
		si7.submit()
		
		# setting so that _test function works
		si7.doc.posting_date = today
		self._test_recurring_invoice(si7, True)

	def _test_recurring_invoice(self, base_si, first_and_last_day):
		from frappe.utils import add_months, get_last_day
		from erpnext.accounts.doctype.sales_invoice.sales_invoice \
			import manage_recurring_invoices, get_next_date
		
		no_of_months = ({"Monthly": 1, "Quarterly": 3, "Yearly": 12})[base_si.doc.recurring_type]
		
		def _test(i):
			self.assertEquals(i+1, frappe.conn.sql("""select count(*) from `tabSales Invoice`
				where recurring_id=%s and docstatus=1""", base_si.doc.recurring_id)[0][0])
			
			next_date = get_next_date(base_si.doc.posting_date, no_of_months, 
				base_si.doc.repeat_on_day_of_month)

			manage_recurring_invoices(next_date=next_date, commit=False)
			
			recurred_invoices = frappe.conn.sql("""select name from `tabSales Invoice`
				where recurring_id=%s and docstatus=1 order by name desc""",
				base_si.doc.recurring_id)
			
			self.assertEquals(i+2, len(recurred_invoices))
			
			new_si = frappe.bean("Sales Invoice", recurred_invoices[0][0])
			
			for fieldname in ["convert_into_recurring_invoice", "recurring_type",
				"repeat_on_day_of_month", "notification_email_address"]:
					self.assertEquals(base_si.doc.fields.get(fieldname),
						new_si.doc.fields.get(fieldname))

			self.assertEquals(new_si.doc.posting_date, unicode(next_date))
			
			self.assertEquals(new_si.doc.invoice_period_from_date,
				unicode(add_months(base_si.doc.invoice_period_from_date, no_of_months)))
			
			if first_and_last_day:
				self.assertEquals(new_si.doc.invoice_period_to_date, 
					unicode(get_last_day(add_months(base_si.doc.invoice_period_to_date,
						no_of_months))))
			else:
				self.assertEquals(new_si.doc.invoice_period_to_date, 
					unicode(add_months(base_si.doc.invoice_period_to_date, no_of_months)))
					
			
			return new_si
		
		# if yearly, test 1 repetition, else test 5 repetitions
		count = 1 if (no_of_months == 12) else 5
		for i in xrange(count):
			base_si = _test(i)
			
	def clear_stock_account_balance(self):
		frappe.conn.sql("delete from `tabStock Ledger Entry`")
		frappe.conn.sql("delete from tabBin")
		frappe.conn.sql("delete from `tabGL Entry`")

	def test_serialized(self):
		from erpnext.stock.doctype.stock_entry.test_stock_entry import make_serialized_item
		from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
		
		se = make_serialized_item()
		serial_nos = get_serial_nos(se.doclist[1].serial_no)
		
		si = frappe.bean(copy=test_records[0])
		si.doc.update_stock = 1
		si.doclist[1].item_code = "_Test Serialized Item With Series"
		si.doclist[1].qty = 1
		si.doclist[1].serial_no = serial_nos[0]
		si.insert()
		si.submit()
		
		self.assertEquals(frappe.conn.get_value("Serial No", serial_nos[0], "status"), "Delivered")
		self.assertFalse(frappe.conn.get_value("Serial No", serial_nos[0], "warehouse"))
		self.assertEquals(frappe.conn.get_value("Serial No", serial_nos[0], 
			"delivery_document_no"), si.doc.name)
			
		return si
			
	def test_serialized_cancel(self):
		from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
		si = self.test_serialized()
		si.cancel()

		serial_nos = get_serial_nos(si.doclist[1].serial_no)

		self.assertEquals(frappe.conn.get_value("Serial No", serial_nos[0], "status"), "Available")
		self.assertEquals(frappe.conn.get_value("Serial No", serial_nos[0], "warehouse"), "_Test Warehouse - _TC")
		self.assertFalse(frappe.conn.get_value("Serial No", serial_nos[0], 
			"delivery_document_no"))

	def test_serialize_status(self):
		from erpnext.stock.doctype.serial_no.serial_no import SerialNoStatusError, get_serial_nos
		from erpnext.stock.doctype.stock_entry.test_stock_entry import make_serialized_item
		
		se = make_serialized_item()
		serial_nos = get_serial_nos(se.doclist[1].serial_no)
		
		sr = frappe.bean("Serial No", serial_nos[0])
		sr.doc.status = "Not Available"
		sr.save()
		
		si = frappe.bean(copy=test_records[0])
		si.doc.update_stock = 1
		si.doclist[1].item_code = "_Test Serialized Item With Series"
		si.doclist[1].qty = 1
		si.doclist[1].serial_no = serial_nos[0]
		si.insert()

		self.assertRaises(SerialNoStatusError, si.submit)

test_dependencies = ["Journal Voucher", "POS Setting", "Contact", "Address"]

test_records = [
	[
		{
			"naming_series": "_T-Sales Invoice-",
			"company": "_Test Company", 
			"is_pos": 0,
			"conversion_rate": 1.0, 
			"currency": "INR", 
			"debit_to": "_Test Customer - _TC",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"doctype": "Sales Invoice", 
			"due_date": "2013-01-23", 
			"fiscal_year": "_Test Fiscal Year 2013", 
			"grand_total": 561.8, 
			"grand_total_export": 561.8, 
			"net_total": 500.0, 
			"plc_conversion_rate": 1.0, 
			"posting_date": "2013-01-23", 
			"price_list_currency": "INR", 
			"selling_price_list": "_Test Price List", 
			"territory": "_Test Territory"
		}, 
		{
			"base_amount": 500.0, 
			"base_rate": 500.0, 
			"description": "138-CMS Shoe", 
			"doctype": "Sales Invoice Item", 
			"amount": 500.0, 
			"rate": 500.0, 
			"income_account": "Sales - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"item_name": "138-CMS Shoe", 
			"parentfield": "entries",
			"qty": 1.0
		}, 
		{
			"account_head": "_Test Account VAT - _TC", 
			"charge_type": "On Net Total", 
			"description": "VAT", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"rate": 6,
		}, 
		{
			"account_head": "_Test Account Service Tax - _TC", 
			"charge_type": "On Net Total", 
			"description": "Service Tax", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"rate": 6.36,
		},
		{
			"parentfield": "sales_team",
			"doctype": "Sales Team",
			"sales_person": "_Test Sales Person 1",
			"allocated_percentage": 65.5,
		},
		{
			"parentfield": "sales_team",
			"doctype": "Sales Team",
			"sales_person": "_Test Sales Person 2",
			"allocated_percentage": 34.5,
		},
	],
	[
		{
			"naming_series": "_T-Sales Invoice-",
			"company": "_Test Company", 
			"is_pos": 0,
			"conversion_rate": 1.0, 
			"currency": "INR", 
			"debit_to": "_Test Customer - _TC",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"doctype": "Sales Invoice", 
			"due_date": "2013-01-23", 
			"fiscal_year": "_Test Fiscal Year 2013", 
			"grand_total": 630.0, 
			"grand_total_export": 630.0, 
			"net_total": 500.0, 
			"plc_conversion_rate": 1.0, 
			"posting_date": "2013-03-07", 
			"price_list_currency": "INR", 
			"selling_price_list": "_Test Price List", 
			"territory": "_Test Territory"
		}, 
		{
			"item_code": "_Test Item",
			"item_name": "_Test Item", 
			"description": "_Test Item", 
			"doctype": "Sales Invoice Item", 
			"parentfield": "entries",
			"qty": 1.0,
			"base_rate": 500.0,
			"base_amount": 500.0, 
			"price_list_rate": 500.0, 
			"amount": 500.0, 
			"income_account": "Sales - _TC",
			"expense_account": "_Test Account Cost for Goods Sold - _TC",
			"cost_center": "_Test Cost Center - _TC",
		}, 
		{
			"account_head": "_Test Account VAT - _TC", 
			"charge_type": "On Net Total", 
			"description": "VAT", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"rate": 16,
		}, 
		{
			"account_head": "_Test Account Service Tax - _TC", 
			"charge_type": "On Net Total", 
			"description": "Service Tax", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"rate": 10
		}
	],
	[
		{
			"naming_series": "_T-Sales Invoice-",
			"company": "_Test Company", 
			"is_pos": 0,
			"conversion_rate": 1.0, 
			"currency": "INR", 
			"debit_to": "_Test Customer - _TC",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"doctype": "Sales Invoice", 
			"due_date": "2013-01-23", 
			"fiscal_year": "_Test Fiscal Year 2013", 
			"grand_total_export": 0, 
			"plc_conversion_rate": 1.0, 
			"posting_date": "2013-01-23", 
			"price_list_currency": "INR", 
			"selling_price_list": "_Test Price List", 
			"territory": "_Test Territory",
		},
		# items
		{
			"doctype": "Sales Invoice Item",
			"parentfield": "entries",
			"item_code": "_Test Item Home Desktop 100",
			"item_name": "_Test Item Home Desktop 100",
			"qty": 10,
			"price_list_rate": 50,
			"rate": 50,
			"stock_uom": "_Test UOM",
			"item_tax_rate": json.dumps({"_Test Account Excise Duty - _TC": 10}),
			"income_account": "Sales - _TC",
			"cost_center": "_Test Cost Center - _TC",
		
		},
		{
			"doctype": "Sales Invoice Item",
			"parentfield": "entries",
			"item_code": "_Test Item Home Desktop 200",
			"item_name": "_Test Item Home Desktop 200",
			"qty": 5,
			"price_list_rate": 150,
			"rate": 150,
			"stock_uom": "_Test UOM",
			"income_account": "Sales - _TC",
			"cost_center": "_Test Cost Center - _TC",
		
		},
		# taxes
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "Actual",
			"account_head": "_Test Account Shipping Charges - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Shipping Charges",
			"rate": 100
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Net Total",
			"account_head": "_Test Account Customs Duty - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Customs Duty",
			"rate": 10
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Net Total",
			"account_head": "_Test Account Excise Duty - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Excise Duty",
			"rate": 12
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Amount",
			"account_head": "_Test Account Education Cess - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Education Cess",
			"rate": 2,
			"row_id": 3
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Amount",
			"account_head": "_Test Account S&H Education Cess - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "S&H Education Cess",
			"rate": 1,
			"row_id": 3
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Total",
			"account_head": "_Test Account CST - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "CST",
			"rate": 2,
			"row_id": 5
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Net Total",
			"account_head": "_Test Account VAT - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "VAT",
			"rate": 12.5
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Total",
			"account_head": "_Test Account Discount - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Discount",
			"rate": -10,
			"row_id": 7
		},
	],
	[
		{
			"naming_series": "_T-Sales Invoice-",
			"company": "_Test Company", 
			"is_pos": 0,
			"conversion_rate": 1.0, 
			"currency": "INR", 
			"debit_to": "_Test Customer - _TC",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"doctype": "Sales Invoice", 
			"due_date": "2013-01-23", 
			"fiscal_year": "_Test Fiscal Year 2013", 
			"grand_total_export": 0, 
			"plc_conversion_rate": 1.0, 
			"posting_date": "2013-01-23", 
			"price_list_currency": "INR", 
			"selling_price_list": "_Test Price List", 
			"territory": "_Test Territory",
		},
		# items
		{
			"doctype": "Sales Invoice Item",
			"parentfield": "entries",
			"item_code": "_Test Item Home Desktop 100",
			"item_name": "_Test Item Home Desktop 100",
			"qty": 10,
			"price_list_rate": 62.5,
			"stock_uom": "_Test UOM",
			"item_tax_rate": json.dumps({"_Test Account Excise Duty - _TC": 10}),
			"income_account": "Sales - _TC",
			"cost_center": "_Test Cost Center - _TC",
		
		},
		{
			"doctype": "Sales Invoice Item",
			"parentfield": "entries",
			"item_code": "_Test Item Home Desktop 200",
			"item_name": "_Test Item Home Desktop 200",
			"qty": 5,
			"price_list_rate": 190.66,
			"stock_uom": "_Test UOM",
			"income_account": "Sales - _TC",
			"cost_center": "_Test Cost Center - _TC",
		
		},
		# taxes
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Net Total",
			"account_head": "_Test Account Excise Duty - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Excise Duty",
			"rate": 12,
			"included_in_print_rate": 1,
			"idx": 1
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Amount",
			"account_head": "_Test Account Education Cess - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Education Cess",
			"rate": 2,
			"row_id": 1,
			"included_in_print_rate": 1,
			"idx": 2
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Amount",
			"account_head": "_Test Account S&H Education Cess - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "S&H Education Cess",
			"rate": 1,
			"row_id": 1,
			"included_in_print_rate": 1,
			"idx": 3
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Total",
			"account_head": "_Test Account CST - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "CST",
			"rate": 2,
			"row_id": 3,
			"included_in_print_rate": 1,
			"idx": 4
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Net Total",
			"account_head": "_Test Account VAT - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "VAT",
			"rate": 12.5,
			"included_in_print_rate": 1,
			"idx": 5
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Net Total",
			"account_head": "_Test Account Customs Duty - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Customs Duty",
			"rate": 10,
			"idx": 6
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "Actual",
			"account_head": "_Test Account Shipping Charges - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Shipping Charges",
			"rate": 100,
			"idx": 7
		},
		{
			"doctype": "Sales Taxes and Charges",
			"parentfield": "other_charges",
			"charge_type": "On Previous Row Total",
			"account_head": "_Test Account Discount - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"description": "Discount",
			"rate": -10,
			"row_id": 7,
			"idx": 8
		},
	],
]