# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, unittest
from frappe.utils import flt
from erpnext.stock.doctype.serial_no.serial_no import *
from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt import set_perpetual_inventory
from erpnext.stock.doctype.stock_ledger_entry.stock_ledger_entry import StockFreezeError

class TestStockEntry(unittest.TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		set_perpetual_inventory(0)
		if hasattr(self, "old_default_company"):
			frappe.conn.set_default("company", self.old_default_company)

	def test_auto_material_request(self):
		frappe.conn.sql("""delete from `tabMaterial Request Item`""")
		frappe.conn.sql("""delete from `tabMaterial Request`""")
		self._clear_stock_account_balance()

		frappe.conn.set_value("Stock Settings", None, "auto_indent", True)

		st1 = frappe.bean(copy=test_records[0])
		st1.insert()
		st1.submit()

		st2 = frappe.bean(copy=test_records[1])
		st2.insert()
		st2.submit()
				
		from erpnext.stock.utils import reorder_item

		reorder_item()

		mr_name = frappe.conn.sql("""select parent from `tabMaterial Request Item`
			where item_code='_Test Item'""")

		self.assertTrue(mr_name)

		frappe.conn.set_default("company", self.old_default_company)

	def test_material_receipt_gl_entry(self):
		self._clear_stock_account_balance()
		set_perpetual_inventory()

		mr = frappe.bean(copy=test_records[0])
		mr.insert()
		mr.submit()

		stock_in_hand_account = frappe.conn.get_value("Account", {"account_type": "Warehouse",
			"master_name": mr.doclist[1].t_warehouse})

		self.check_stock_ledger_entries("Stock Entry", mr.doc.name,
			[["_Test Item", "_Test Warehouse - _TC", 50.0]])

		self.check_gl_entries("Stock Entry", mr.doc.name,
			sorted([
				[stock_in_hand_account, 5000.0, 0.0],
				["Stock Adjustment - _TC", 0.0, 5000.0]
			])
		)

		mr.cancel()

		self.assertFalse(frappe.conn.sql("""select * from `tabStock Ledger Entry`
			where voucher_type='Stock Entry' and voucher_no=%s""", mr.doc.name))

		self.assertFalse(frappe.conn.sql("""select * from `tabGL Entry`
			where voucher_type='Stock Entry' and voucher_no=%s""", mr.doc.name))


	def test_material_issue_gl_entry(self):
		self._clear_stock_account_balance()
		set_perpetual_inventory()

		self._insert_material_receipt()

		mi = frappe.bean(copy=test_records[1])
		mi.insert()
		mi.submit()

		self.check_stock_ledger_entries("Stock Entry", mi.doc.name,
			[["_Test Item", "_Test Warehouse - _TC", -40.0]])

		stock_in_hand_account = frappe.conn.get_value("Account", {"account_type": "Warehouse",
			"master_name": mi.doclist[1].s_warehouse})

		self.check_gl_entries("Stock Entry", mi.doc.name,
			sorted([
				[stock_in_hand_account, 0.0, 4000.0],
				["Stock Adjustment - _TC", 4000.0, 0.0]
			])
		)

		mi.cancel()
		self.assertFalse(frappe.conn.sql("""select * from `tabStock Ledger Entry`
			where voucher_type='Stock Entry' and voucher_no=%s""", mi.doc.name))

		self.assertFalse(frappe.conn.sql("""select * from `tabGL Entry`
			where voucher_type='Stock Entry' and voucher_no=%s""", mi.doc.name))

		self.assertEquals(frappe.conn.get_value("Bin", {"warehouse": mi.doclist[1].s_warehouse,
			"item_code": mi.doclist[1].item_code}, "actual_qty"), 50)

		self.assertEquals(frappe.conn.get_value("Bin", {"warehouse": mi.doclist[1].s_warehouse,
			"item_code": mi.doclist[1].item_code}, "stock_value"), 5000)

	def test_material_transfer_gl_entry(self):
		self._clear_stock_account_balance()
		set_perpetual_inventory()

		self._insert_material_receipt()

		mtn = frappe.bean(copy=test_records[2])
		mtn.insert()
		mtn.submit()

		self.check_stock_ledger_entries("Stock Entry", mtn.doc.name,
			[["_Test Item", "_Test Warehouse - _TC", -45.0], ["_Test Item", "_Test Warehouse 1 - _TC", 45.0]])

		stock_in_hand_account = frappe.conn.get_value("Account", {"account_type": "Warehouse",
			"master_name": mtn.doclist[1].s_warehouse})

		fixed_asset_account = frappe.conn.get_value("Account", {"account_type": "Warehouse",
			"master_name": mtn.doclist[1].t_warehouse})


		self.check_gl_entries("Stock Entry", mtn.doc.name,
			sorted([
				[stock_in_hand_account, 0.0, 4500.0],
				[fixed_asset_account, 4500.0, 0.0],
			])
		)


		mtn.cancel()
		self.assertFalse(frappe.conn.sql("""select * from `tabStock Ledger Entry`
			where voucher_type='Stock Entry' and voucher_no=%s""", mtn.doc.name))

		self.assertFalse(frappe.conn.sql("""select * from `tabGL Entry`
			where voucher_type='Stock Entry' and voucher_no=%s""", mtn.doc.name))


	def test_repack_no_change_in_valuation(self):
		self._clear_stock_account_balance()
		set_perpetual_inventory()

		self._insert_material_receipt()

		repack = frappe.bean(copy=test_records[3])
		repack.insert()
		repack.submit()

		self.check_stock_ledger_entries("Stock Entry", repack.doc.name,
			[["_Test Item", "_Test Warehouse - _TC", -50.0],
				["_Test Item Home Desktop 100", "_Test Warehouse - _TC", 1]])

		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Stock Entry' and voucher_no=%s
			order by account desc""", repack.doc.name, as_dict=1)
		self.assertFalse(gl_entries)

		set_perpetual_inventory(0)

	def test_repack_with_change_in_valuation(self):
		self._clear_stock_account_balance()
		set_perpetual_inventory()

		self._insert_material_receipt()

		repack = frappe.bean(copy=test_records[3])
		repack.doclist[2].incoming_rate = 6000
		repack.insert()
		repack.submit()

		stock_in_hand_account = frappe.conn.get_value("Account", {"account_type": "Warehouse",
			"master_name": repack.doclist[2].t_warehouse})

		self.check_gl_entries("Stock Entry", repack.doc.name,
			sorted([
				[stock_in_hand_account, 1000.0, 0.0],
				["Stock Adjustment - _TC", 0.0, 1000.0],
			])
		)
		set_perpetual_inventory(0)

	def check_stock_ledger_entries(self, voucher_type, voucher_no, expected_sle):
		expected_sle.sort(key=lambda x: x[0])

		# check stock ledger entries
		sle = frappe.conn.sql("""select item_code, warehouse, actual_qty
			from `tabStock Ledger Entry` where voucher_type = %s
			and voucher_no = %s order by item_code, warehouse, actual_qty""",
			(voucher_type, voucher_no), as_list=1)
		self.assertTrue(sle)
		sle.sort(key=lambda x: x[0])

		for i, sle in enumerate(sle):
			self.assertEquals(expected_sle[i][0], sle[0])
			self.assertEquals(expected_sle[i][1], sle[1])
			self.assertEquals(expected_sle[i][2], sle[2])

	def check_gl_entries(self, voucher_type, voucher_no, expected_gl_entries):
		expected_gl_entries.sort(key=lambda x: x[0])

		gl_entries = frappe.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type=%s and voucher_no=%s
			order by account asc, debit asc""", (voucher_type, voucher_no), as_list=1)
		self.assertTrue(gl_entries)
		gl_entries.sort(key=lambda x: x[0])

		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_gl_entries[i][0], gle[0])
			self.assertEquals(expected_gl_entries[i][1], gle[1])
			self.assertEquals(expected_gl_entries[i][2], gle[2])

	def _insert_material_receipt(self):
		self._clear_stock_account_balance()
		se1 = frappe.bean(copy=test_records[0])
		se1.insert()
		se1.submit()

		se2 = frappe.bean(copy=test_records[0])
		se2.doclist[1].item_code = "_Test Item Home Desktop 100"
		se2.insert()
		se2.submit()

		frappe.conn.set_default("company", self.old_default_company)

	def _get_actual_qty(self):
		return flt(frappe.conn.get_value("Bin", {"item_code": "_Test Item",
			"warehouse": "_Test Warehouse - _TC"}, "actual_qty"))

	def _test_sales_invoice_return(self, item_code, delivered_qty, returned_qty):
		from erpnext.stock.doctype.stock_entry.stock_entry import NotUpdateStockError
		
		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice \
			import test_records as sales_invoice_test_records

		# invalid sales invoice as update stock not checked
		si = frappe.bean(copy=sales_invoice_test_records[1])
		si.insert()
		si.submit()

		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Sales Return"
		se.doc.sales_invoice_no = si.doc.name
		se.doclist[1].qty = returned_qty
		se.doclist[1].transfer_qty = returned_qty
		self.assertRaises(NotUpdateStockError, se.insert)

		self._insert_material_receipt()

		# check currency available qty in bin
		actual_qty_0 = self._get_actual_qty()

		# insert a pos invoice with update stock
		si = frappe.bean(copy=sales_invoice_test_records[1])
		si.doc.is_pos = si.doc.update_stock = 1
		si.doclist[1].warehouse = "_Test Warehouse - _TC"
		si.doclist[1].item_code = item_code
		si.doclist[1].qty = 5.0
		si.insert()
		si.submit()

		# check available bin qty after invoice submission
		actual_qty_1 = self._get_actual_qty()

		self.assertEquals(actual_qty_0 - delivered_qty, actual_qty_1)

		# check if item is validated
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Sales Return"
		se.doc.sales_invoice_no = si.doc.name
		se.doc.posting_date = "2013-03-10"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doclist[1].item_code = "_Test Item Home Desktop 200"
		se.doclist[1].qty = returned_qty
		se.doclist[1].transfer_qty = returned_qty

		# check if stock entry gets submitted
		self.assertRaises(frappe.DoesNotExistError, se.insert)

		# try again
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Sales Return"
		se.doc.posting_date = "2013-03-10"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doc.sales_invoice_no = si.doc.name
		se.doclist[1].qty = returned_qty
		se.doclist[1].transfer_qty = returned_qty
		# in both cases item code remains _Test Item when returning
		se.insert()

		se.submit()

		# check if available qty is increased
		actual_qty_2 = self._get_actual_qty()

		self.assertEquals(actual_qty_1 + returned_qty, actual_qty_2)

		return se

	def test_sales_invoice_return_of_non_packing_item(self):
		self._clear_stock_account_balance()
		self._test_sales_invoice_return("_Test Item", 5, 2)

	def test_sales_invoice_return_of_packing_item(self):
		self._clear_stock_account_balance()
		self._test_sales_invoice_return("_Test Sales BOM Item", 25, 20)

	def _test_delivery_note_return(self, item_code, delivered_qty, returned_qty):
		self._insert_material_receipt()

		from erpnext.stock.doctype.delivery_note.test_delivery_note \
			import test_records as delivery_note_test_records

		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		actual_qty_0 = self._get_actual_qty()
		# make a delivery note based on this invoice
		dn = frappe.bean(copy=delivery_note_test_records[0])
		dn.doclist[1].item_code = item_code
		dn.insert()
		dn.submit()

		actual_qty_1 = self._get_actual_qty()

		self.assertEquals(actual_qty_0 - delivered_qty, actual_qty_1)

		si_doclist = make_sales_invoice(dn.doc.name)

		si = frappe.bean(si_doclist)
		si.doc.posting_date = dn.doc.posting_date
		si.doc.debit_to = "_Test Customer - _TC"
		for d in si.doclist.get({"parentfield": "entries"}):
			d.income_account = "Sales - _TC"
			d.cost_center = "_Test Cost Center - _TC"
		si.insert()
		si.submit()

		# insert and submit stock entry for sales return
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Sales Return"
		se.doc.delivery_note_no = dn.doc.name
		se.doc.posting_date = "2013-03-10"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doclist[1].qty = se.doclist[1].transfer_qty = returned_qty

		se.insert()
		se.submit()

		actual_qty_2 = self._get_actual_qty()
		self.assertEquals(actual_qty_1 + returned_qty, actual_qty_2)

		return se

	def test_delivery_note_return_of_non_packing_item(self):
		self._clear_stock_account_balance()
		self._test_delivery_note_return("_Test Item", 5, 2)

	def test_delivery_note_return_of_packing_item(self):
		self._clear_stock_account_balance()
		self._test_delivery_note_return("_Test Sales BOM Item", 25, 20)

	def _test_sales_return_jv(self, se):
		from erpnext.stock.doctype.stock_entry.stock_entry import make_return_jv
		jv_list = make_return_jv(se.doc.name)

		self.assertEqual(len(jv_list), 3)
		self.assertEqual(jv_list[0].get("voucher_type"), "Credit Note")
		self.assertEqual(jv_list[0].get("posting_date"), se.doc.posting_date)
		self.assertEqual(jv_list[1].get("account"), "_Test Customer - _TC")
		self.assertEqual(jv_list[2].get("account"), "Sales - _TC")
		self.assertTrue(jv_list[1].get("against_invoice"))

	def test_make_return_jv_for_sales_invoice_non_packing_item(self):
		self._clear_stock_account_balance()
		se = self._test_sales_invoice_return("_Test Item", 5, 2)
		self._test_sales_return_jv(se)

	def test_make_return_jv_for_sales_invoice_packing_item(self):
		self._clear_stock_account_balance()
		se = self._test_sales_invoice_return("_Test Sales BOM Item", 25, 20)
		self._test_sales_return_jv(se)

	def test_make_return_jv_for_delivery_note_non_packing_item(self):
		self._clear_stock_account_balance()
		se = self._test_delivery_note_return("_Test Item", 5, 2)
		self._test_sales_return_jv(se)

		se = self._test_delivery_note_return_against_sales_order("_Test Item", 5, 2)
		self._test_sales_return_jv(se)

	def test_make_return_jv_for_delivery_note_packing_item(self):
		self._clear_stock_account_balance()
		se = self._test_delivery_note_return("_Test Sales BOM Item", 25, 20)
		self._test_sales_return_jv(se)

		se = self._test_delivery_note_return_against_sales_order("_Test Sales BOM Item", 25, 20)
		self._test_sales_return_jv(se)

	def _test_delivery_note_return_against_sales_order(self, item_code, delivered_qty, returned_qty):
		self._insert_material_receipt()

		from erpnext.selling.doctype.sales_order.test_sales_order import test_records as sales_order_test_records
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice, make_delivery_note

		actual_qty_0 = self._get_actual_qty()

		so = frappe.bean(copy=sales_order_test_records[0])
		so.doclist[1].item_code = item_code
		so.doclist[1].qty = 5.0
		so.insert()
		so.submit()

		dn_doclist = make_delivery_note(so.doc.name)

		dn = frappe.bean(dn_doclist)
		dn.doc.status = "Draft"
		dn.doc.posting_date = so.doc.delivery_date
		dn.insert()
		dn.submit()

		actual_qty_1 = self._get_actual_qty()

		self.assertEquals(actual_qty_0 - delivered_qty, actual_qty_1)

		si_doclist = make_sales_invoice(so.doc.name)

		si = frappe.bean(si_doclist)
		si.doc.posting_date = dn.doc.posting_date
		si.doc.debit_to = "_Test Customer - _TC"
		for d in si.doclist.get({"parentfield": "entries"}):
			d.income_account = "Sales - _TC"
			d.cost_center = "_Test Cost Center - _TC"
		si.insert()
		si.submit()

		# insert and submit stock entry for sales return
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Sales Return"
		se.doc.delivery_note_no = dn.doc.name
		se.doc.posting_date = "2013-03-10"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doclist[1].qty = se.doclist[1].transfer_qty = returned_qty

		se.insert()
		se.submit()

		actual_qty_2 = self._get_actual_qty()
		self.assertEquals(actual_qty_1 + returned_qty, actual_qty_2)

		return se

	def test_purchase_receipt_return(self):
		self._clear_stock_account_balance()

		actual_qty_0 = self._get_actual_qty()

		from erpnext.stock.doctype.purchase_receipt.test_purchase_receipt \
			import test_records as purchase_receipt_test_records

		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
		
		# submit purchase receipt
		pr = frappe.bean(copy=purchase_receipt_test_records[0])
		pr.insert()
		pr.submit()

		actual_qty_1 = self._get_actual_qty()

		self.assertEquals(actual_qty_0 + 5, actual_qty_1)

		pi_doclist = make_purchase_invoice(pr.doc.name)

		pi = frappe.bean(pi_doclist)
		pi.doc.posting_date = pr.doc.posting_date
		pi.doc.credit_to = "_Test Supplier - _TC"
		for d in pi.doclist.get({"parentfield": "entries"}):
			d.expense_account = "_Test Account Cost for Goods Sold - _TC"
			d.cost_center = "_Test Cost Center - _TC"

		for d in pi.doclist.get({"parentfield": "other_charges"}):
			d.cost_center = "_Test Cost Center - _TC"

		pi.run_method("calculate_taxes_and_totals")
		pi.doc.bill_no = "NA"
		pi.insert()
		pi.submit()

		# submit purchase return
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Purchase Return"
		se.doc.purchase_receipt_no = pr.doc.name
		se.doc.posting_date = "2013-03-01"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doclist[1].qty = se.doclist[1].transfer_qty = 5
		se.doclist[1].s_warehouse = "_Test Warehouse - _TC"
		se.insert()
		se.submit()

		actual_qty_2 = self._get_actual_qty()

		self.assertEquals(actual_qty_1 - 5, actual_qty_2)

		frappe.conn.set_default("company", self.old_default_company)

		return se, pr.doc.name

	def test_over_stock_return(self):
		from erpnext.stock.doctype.stock_entry.stock_entry import StockOverReturnError
		self._clear_stock_account_balance()

		# out of 10, 5 gets returned
		prev_se, pr_docname = self.test_purchase_receipt_return()

		# submit purchase return - return another 6 qtys so that exception is raised
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Purchase Return"
		se.doc.purchase_receipt_no = pr_docname
		se.doc.posting_date = "2013-03-01"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doclist[1].qty = se.doclist[1].transfer_qty = 6
		se.doclist[1].s_warehouse = "_Test Warehouse - _TC"

		self.assertRaises(StockOverReturnError, se.insert)

	def _test_purchase_return_jv(self, se):
		from erpnext.stock.doctype.stock_entry.stock_entry import make_return_jv
		jv_list = make_return_jv(se.doc.name)

		self.assertEqual(len(jv_list), 3)
		self.assertEqual(jv_list[0].get("voucher_type"), "Debit Note")
		self.assertEqual(jv_list[0].get("posting_date"), se.doc.posting_date)
		self.assertEqual(jv_list[1].get("account"), "_Test Supplier - _TC")
		self.assertEqual(jv_list[2].get("account"), "_Test Account Cost for Goods Sold - _TC")
		self.assertTrue(jv_list[1].get("against_voucher"))

	def test_make_return_jv_for_purchase_receipt(self):
		self._clear_stock_account_balance()
		se, pr_name = self.test_purchase_receipt_return()
		self._test_purchase_return_jv(se)

		se, pr_name = self._test_purchase_return_return_against_purchase_order()
		self._test_purchase_return_jv(se)

	def _test_purchase_return_return_against_purchase_order(self):
		self._clear_stock_account_balance()

		actual_qty_0 = self._get_actual_qty()
		
		from erpnext.buying.doctype.purchase_order.test_purchase_order \
			import test_records as purchase_order_test_records
		
		from erpnext.buying.doctype.purchase_order.purchase_order import \
			make_purchase_receipt, make_purchase_invoice

		# submit purchase receipt
		po = frappe.bean(copy=purchase_order_test_records[0])
		po.doc.is_subcontracted = None
		po.doclist[1].item_code = "_Test Item"
		po.doclist[1].rate = 50
		po.insert()
		po.submit()

		pr_doclist = make_purchase_receipt(po.doc.name)

		pr = frappe.bean(pr_doclist)
		pr.doc.posting_date = po.doc.transaction_date
		pr.insert()
		pr.submit()

		actual_qty_1 = self._get_actual_qty()

		self.assertEquals(actual_qty_0 + 10, actual_qty_1)

		pi_doclist = make_purchase_invoice(po.doc.name)

		pi = frappe.bean(pi_doclist)
		pi.doc.posting_date = pr.doc.posting_date
		pi.doc.credit_to = "_Test Supplier - _TC"
		for d in pi.doclist.get({"parentfield": "entries"}):
			d.expense_account = "_Test Account Cost for Goods Sold - _TC"
			d.cost_center = "_Test Cost Center - _TC"
		for d in pi.doclist.get({"parentfield": "other_charges"}):
			d.cost_center = "_Test Cost Center - _TC"

		pi.run_method("calculate_taxes_and_totals")
		pi.doc.bill_no = "NA"
		pi.insert()
		pi.submit()

		# submit purchase return
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Purchase Return"
		se.doc.purchase_receipt_no = pr.doc.name
		se.doc.posting_date = "2013-03-01"
		se.doc.fiscal_year = "_Test Fiscal Year 2013"
		se.doclist[1].qty = se.doclist[1].transfer_qty = 5
		se.doclist[1].s_warehouse = "_Test Warehouse - _TC"
		se.insert()
		se.submit()

		actual_qty_2 = self._get_actual_qty()

		self.assertEquals(actual_qty_1 - 5, actual_qty_2)

		frappe.conn.set_default("company", self.old_default_company)

		return se, pr.doc.name

	def _clear_stock_account_balance(self):
		frappe.conn.sql("delete from `tabStock Ledger Entry`")
		frappe.conn.sql("""delete from `tabBin`""")
		frappe.conn.sql("""delete from `tabGL Entry`""")

		self.old_default_company = frappe.conn.get_default("company")
		frappe.conn.set_default("company", "_Test Company")

	def test_serial_no_not_reqd(self):
		se = frappe.bean(copy=test_records[0])
		se.doclist[1].serial_no = "ABCD"
		se.insert()
		self.assertRaises(SerialNoNotRequiredError, se.submit)

	def test_serial_no_reqd(self):
		se = frappe.bean(copy=test_records[0])
		se.doclist[1].item_code = "_Test Serialized Item"
		se.doclist[1].qty = 2
		se.doclist[1].transfer_qty = 2
		se.insert()
		self.assertRaises(SerialNoRequiredError, se.submit)

	def test_serial_no_qty_more(self):
		se = frappe.bean(copy=test_records[0])
		se.doclist[1].item_code = "_Test Serialized Item"
		se.doclist[1].qty = 2
		se.doclist[1].serial_no = "ABCD\nEFGH\nXYZ"
		se.doclist[1].transfer_qty = 2
		se.insert()
		self.assertRaises(SerialNoQtyError, se.submit)

	def test_serial_no_qty_less(self):
		se = frappe.bean(copy=test_records[0])
		se.doclist[1].item_code = "_Test Serialized Item"
		se.doclist[1].qty = 2
		se.doclist[1].serial_no = "ABCD"
		se.doclist[1].transfer_qty = 2
		se.insert()
		self.assertRaises(SerialNoQtyError, se.submit)

	def test_serial_no_transfer_in(self):
		self._clear_stock_account_balance()
		se = frappe.bean(copy=test_records[0])
		se.doclist[1].item_code = "_Test Serialized Item"
		se.doclist[1].qty = 2
		se.doclist[1].serial_no = "ABCD\nEFGH"
		se.doclist[1].transfer_qty = 2
		se.insert()
		se.submit()

		self.assertTrue(frappe.conn.exists("Serial No", "ABCD"))
		self.assertTrue(frappe.conn.exists("Serial No", "EFGH"))

		se.cancel()
		self.assertFalse(frappe.conn.get_value("Serial No", "ABCD", "warehouse"))

	def test_serial_no_not_exists(self):
		self._clear_stock_account_balance()
		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Material Issue"
		se.doclist[1].item_code = "_Test Serialized Item"
		se.doclist[1].qty = 2
		se.doclist[1].s_warehouse = "_Test Warehouse 1 - _TC"
		se.doclist[1].t_warehouse = None
		se.doclist[1].serial_no = "ABCD\nEFGH"
		se.doclist[1].transfer_qty = 2
		se.insert()
		self.assertRaises(SerialNoNotExistsError, se.submit)

	def test_serial_duplicate(self):
		self._clear_stock_account_balance()
		self.test_serial_by_series()

		se = frappe.bean(copy=test_records[0])
		se.doclist[1].item_code = "_Test Serialized Item With Series"
		se.doclist[1].qty = 1
		se.doclist[1].serial_no = "ABCD00001"
		se.doclist[1].transfer_qty = 1
		se.insert()
		self.assertRaises(SerialNoDuplicateError, se.submit)

	def test_serial_by_series(self):
		self._clear_stock_account_balance()
		se = make_serialized_item()

		serial_nos = get_serial_nos(se.doclist[1].serial_no)

		self.assertTrue(frappe.conn.exists("Serial No", serial_nos[0]))
		self.assertTrue(frappe.conn.exists("Serial No", serial_nos[1]))

		return se

	def test_serial_item_error(self):
		self._clear_stock_account_balance()
		self.test_serial_by_series()

		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Material Transfer"
		se.doclist[1].item_code = "_Test Serialized Item"
		se.doclist[1].qty = 1
		se.doclist[1].transfer_qty = 1
		se.doclist[1].serial_no = "ABCD00001"
		se.doclist[1].s_warehouse = "_Test Warehouse - _TC"
		se.doclist[1].t_warehouse = "_Test Warehouse 1 - _TC"
		se.insert()
		self.assertRaises(SerialNoItemError, se.submit)

	def test_serial_move(self):
		self._clear_stock_account_balance()
		se = make_serialized_item()
		serial_no = get_serial_nos(se.doclist[1].serial_no)[0]

		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Material Transfer"
		se.doclist[1].item_code = "_Test Serialized Item With Series"
		se.doclist[1].qty = 1
		se.doclist[1].transfer_qty = 1
		se.doclist[1].serial_no = serial_no
		se.doclist[1].s_warehouse = "_Test Warehouse - _TC"
		se.doclist[1].t_warehouse = "_Test Warehouse 1 - _TC"
		se.insert()
		se.submit()
		self.assertTrue(frappe.conn.get_value("Serial No", serial_no, "warehouse"), "_Test Warehouse 1 - _TC")

		se.cancel()
		self.assertTrue(frappe.conn.get_value("Serial No", serial_no, "warehouse"), "_Test Warehouse - _TC")

	def test_serial_warehouse_error(self):
		self._clear_stock_account_balance()
		make_serialized_item()

		se = frappe.bean(copy=test_records[0])
		se.doc.purpose = "Material Transfer"
		se.doclist[1].item_code = "_Test Serialized Item With Series"
		se.doclist[1].qty = 1
		se.doclist[1].transfer_qty = 1
		se.doclist[1].serial_no = "ABCD00001"
		se.doclist[1].s_warehouse = "_Test Warehouse 1 - _TC"
		se.doclist[1].t_warehouse = "_Test Warehouse - _TC"
		se.insert()
		self.assertRaises(SerialNoWarehouseError, se.submit)

	def test_serial_cancel(self):
		self._clear_stock_account_balance()
		se = self.test_serial_by_series()
		se.cancel()

		serial_no = get_serial_nos(se.doclist[1].serial_no)[0]
		self.assertFalse(frappe.conn.get_value("Serial No", serial_no, "warehouse"))
		
	def test_warehouse_company_validation(self):
		set_perpetual_inventory(0)
		self._clear_stock_account_balance()
		frappe.bean("Profile", "test2@example.com").get_controller()\
			.add_roles("Sales User", "Sales Manager", "Material User", "Material Manager")
		frappe.set_user("test2@example.com")

		from erpnext.stock.utils import InvalidWarehouseCompany
		st1 = frappe.bean(copy=test_records[0])
		st1.doclist[1].t_warehouse="_Test Warehouse 2 - _TC1"
		st1.insert()
		self.assertRaises(InvalidWarehouseCompany, st1.submit)
		
	# permission tests
	def test_warehouse_user(self):
		import frappe.defaults
		from frappe.model.bean import BeanPermissionError
		set_perpetual_inventory(0)
		
		frappe.defaults.add_default("Warehouse", "_Test Warehouse 1 - _TC1", "test@example.com", "Restriction")
		frappe.defaults.add_default("Warehouse", "_Test Warehouse 2 - _TC1", "test2@example.com", "Restriction")
		frappe.bean("Profile", "test@example.com").get_controller()\
			.add_roles("Sales User", "Sales Manager", "Material User", "Material Manager")
		frappe.bean("Profile", "test2@example.com").get_controller()\
			.add_roles("Sales User", "Sales Manager", "Material User", "Material Manager")

		frappe.set_user("test@example.com")
		st1 = frappe.bean(copy=test_records[0])
		st1.doc.company = "_Test Company 1"
		st1.doclist[1].t_warehouse="_Test Warehouse 2 - _TC1"
		self.assertRaises(BeanPermissionError, st1.insert)

		frappe.set_user("test2@example.com")
		st1 = frappe.bean(copy=test_records[0])
		st1.doc.company = "_Test Company 1"
		st1.doclist[1].t_warehouse="_Test Warehouse 2 - _TC1"
		st1.insert()
		st1.submit()
		
		frappe.defaults.clear_default("Warehouse", "_Test Warehouse 1 - _TC1", "test@example.com", parenttype="Restriction")
		frappe.defaults.clear_default("Warehouse", "_Test Warehouse 2 - _TC1", "test2@example.com", parenttype="Restriction")
		
	def test_freeze_stocks (self):
		self._clear_stock_account_balance()
		frappe.conn.set_value('Stock Settings', None,'stock_auth_role', '')

		# test freeze_stocks_upto
		date_newer_than_test_records = add_days(getdate(test_records[0][0]['posting_date']), 5)
		frappe.conn.set_value("Stock Settings", None, "stock_frozen_upto", date_newer_than_test_records)
		se = frappe.bean(copy=test_records[0]).insert()
		self.assertRaises (StockFreezeError, se.submit)
		frappe.conn.set_value("Stock Settings", None, "stock_frozen_upto", '')

		# test freeze_stocks_upto_days
		frappe.conn.set_value("Stock Settings", None, "stock_frozen_upto_days", 7)
		se = frappe.bean(copy=test_records[0]).insert()
		self.assertRaises (StockFreezeError, se.submit)
		frappe.conn.set_value("Stock Settings", None, "stock_frozen_upto_days", 0)

def make_serialized_item():
	se = frappe.bean(copy=test_records[0])
	se.doclist[1].item_code = "_Test Serialized Item With Series"
	se.doclist[1].qty = 2
	se.doclist[1].transfer_qty = 2
	se.insert()
	se.submit()
	return se

test_records = [
	[
		{
			"company": "_Test Company",
			"doctype": "Stock Entry",
			"posting_date": "2013-01-01",
			"posting_time": "17:14:24",
			"purpose": "Material Receipt",
			"fiscal_year": "_Test Fiscal Year 2013",
		},
		{
			"conversion_factor": 1.0,
			"doctype": "Stock Entry Detail",
			"item_code": "_Test Item",
			"parentfield": "mtn_details",
			"incoming_rate": 100,
			"qty": 50.0,
			"stock_uom": "_Test UOM",
			"transfer_qty": 50.0,
			"uom": "_Test UOM",
			"t_warehouse": "_Test Warehouse - _TC",
			"expense_account": "Stock Adjustment - _TC",
			"cost_center": "_Test Cost Center - _TC"
		},
	],
	[
		{
			"company": "_Test Company",
			"doctype": "Stock Entry",
			"posting_date": "2013-01-25",
			"posting_time": "17:15",
			"purpose": "Material Issue",
			"fiscal_year": "_Test Fiscal Year 2013",
		},
		{
			"conversion_factor": 1.0,
			"doctype": "Stock Entry Detail",
			"item_code": "_Test Item",
			"parentfield": "mtn_details",
			"incoming_rate": 100,
			"qty": 40.0,
			"stock_uom": "_Test UOM",
			"transfer_qty": 40.0,
			"uom": "_Test UOM",
			"s_warehouse": "_Test Warehouse - _TC",
			"expense_account": "Stock Adjustment - _TC",
			"cost_center": "_Test Cost Center - _TC"
		},
	],
	[
		{
			"company": "_Test Company",
			"doctype": "Stock Entry",
			"posting_date": "2013-01-25",
			"posting_time": "17:14:24",
			"purpose": "Material Transfer",
			"fiscal_year": "_Test Fiscal Year 2013",
		},
		{
			"conversion_factor": 1.0,
			"doctype": "Stock Entry Detail",
			"item_code": "_Test Item",
			"parentfield": "mtn_details",
			"incoming_rate": 100,
			"qty": 45.0,
			"stock_uom": "_Test UOM",
			"transfer_qty": 45.0,
			"uom": "_Test UOM",
			"s_warehouse": "_Test Warehouse - _TC",
			"t_warehouse": "_Test Warehouse 1 - _TC",
			"expense_account": "Stock Adjustment - _TC",
			"cost_center": "_Test Cost Center - _TC"
		}
	],
	[
		{
			"company": "_Test Company",
			"doctype": "Stock Entry",
			"posting_date": "2013-01-25",
			"posting_time": "17:14:24",
			"purpose": "Manufacture/Repack",
			"fiscal_year": "_Test Fiscal Year 2013",
		},
		{
			"conversion_factor": 1.0,
			"doctype": "Stock Entry Detail",
			"item_code": "_Test Item",
			"parentfield": "mtn_details",
			"incoming_rate": 100,
			"qty": 50.0,
			"stock_uom": "_Test UOM",
			"transfer_qty": 50.0,
			"uom": "_Test UOM",
			"s_warehouse": "_Test Warehouse - _TC",
			"expense_account": "Stock Adjustment - _TC",
			"cost_center": "_Test Cost Center - _TC"
		},
		{
			"conversion_factor": 1.0,
			"doctype": "Stock Entry Detail",
			"item_code": "_Test Item Home Desktop 100",
			"parentfield": "mtn_details",
			"incoming_rate": 5000,
			"qty": 1,
			"stock_uom": "_Test UOM",
			"transfer_qty": 1,
			"uom": "_Test UOM",
			"t_warehouse": "_Test Warehouse - _TC",
			"expense_account": "Stock Adjustment - _TC",
			"cost_center": "_Test Cost Center - _TC"
		},
	],
]
