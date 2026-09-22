import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = "ruigandh-pos-secret"
DB_NAME = "ruigandh.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sku TEXT UNIQUE,
                cost_price REAL DEFAULT 0,
                selling_price REAL NOT NULL,
                stock_qty INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT UNIQUE NOT NULL,
                customer_name TEXT,
                customer_phone TEXT,
                total_amount REAL NOT NULL,
                payment_mode TEXT DEFAULT 'Cash',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                unit_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)

# Initialize database tables on load so Gunicorn creates tables automatically
init_db()

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ruigandh | Inventory & Billing</title>
  <style>
    :root {
      --primary: #0f766e;
      --primary-hover: #115e59;
      --bg: #f8fafc;
      --surface: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --danger: #ef4444;
      --success: #10b981;
    }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding-bottom: 2rem; }
    header { background: #042f2e; color: #fff; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
    header h1 { margin: 0; font-size: 1.25rem; letter-spacing: 0.5px; }
    nav a { color: #ccfbf1; text-decoration: none; margin-left: 1.25rem; font-weight: 500; font-size: 0.95rem; }
    nav a:hover { color: #fff; text-decoration: underline; }
    .container { max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .grid { display: grid; gap: 1rem; }
    .grid-2 { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
    .grid-4 { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    label { display: block; font-size: 0.825rem; font-weight: 600; color: var(--muted); margin-bottom: 0.35rem; }
    input, select { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid var(--border); border-radius: 6px; font-size: 0.95rem; outline: none; }
    input:focus, select:focus { border-color: var(--primary); }
    .btn { display: inline-flex; align-items: center; justify-content: center; background: var(--primary); color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; font-weight: 600; cursor: pointer; text-decoration: none; font-size: 0.9rem; gap: 0.5rem; }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary { background: #e2e8f0; color: #334155; }
    .btn-secondary:hover { background: #cbd5e1; }
    .btn-danger { background: var(--danger); }
    .btn-danger:hover { background: #dc2626; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.92rem; }
    th { background: #f1f5f9; color: var(--muted); font-size: 0.8rem; text-transform: uppercase; }
    .badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-ok { background: #dcfce7; color: #166534; }
    .badge-low { background: #fee2e2; color: #991b1b; }
    .flash { background: #f0fdf4; border-left: 4px solid var(--success); color: #166534; padding: 0.75rem 1rem; margin-bottom: 1rem; border-radius: 4px; }
    .flash-error { background: #fef2f2; border-left: 4px solid var(--danger); color: #991b1b; }
    @media print {
      header, .no-print { display: none !important; }
      body { background: white; margin: 0; padding: 0; }
      .container { max-width: 100%; margin: 0; padding: 0; }
      .card { border: none; box-shadow: none; padding: 0; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Ruigandh Billing & Inventory</h1>
    <nav class="no-print">
      <a href="{{ url_for('pos') }}">POS / Quick Bill</a>
      <a href="{{ url_for('inventory') }}">Inventory Master</a>
      <a href="{{ url_for('sales_history') }}">Sales Register</a>
    </nav>
  </header>

  <div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class="flash {% if cat == 'error' %}flash-error{% endif %}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if page == 'pos' %}
      <div class="card">
        <h2 style="margin-top:0;">New Sale Invoice</h2>
        <form method="POST" action="{{ url_for('checkout') }}" id="posForm">
          <div class="grid grid-2" style="margin-bottom: 1.5rem;">
            <div>
              <label>Customer Name</label>
              <input type="text" name="customer_name" placeholder="Walk-in Client">
            </div>
            <div>
              <label>Customer Mobile (for WhatsApp)</label>
              <input type="tel" name="customer_phone" placeholder="e.g. 9876543210">
            </div>
            <div>
              <label>Payment Mode</label>
              <select name="payment_mode">
                <option value="UPI / QR">UPI / QR Code</option>
                <option value="Cash">Cash</option>
                <option value="Card">Debit / Credit Card</option>
              </select>
            </div>
          </div>

          <h3 style="margin-bottom: 0.5rem;">Items</h3>
          <table id="itemsTable">
            <thead>
              <tr>
                <th style="width: 45%;">Item</th>
                <th style="width: 20%;">Price (₹)</th>
                <th style="width: 15%;">Qty</th>
                <th style="width: 15%;">Total (₹)</th>
                <th style="width: 5%;"></th>
              </tr>
            </thead>
            <tbody id="rowsBody">
              <tr class="item-row">
                <td>
                  <select name="item_id[]" class="item-select" required onchange="updateRow(this)">
                    <option value="" data-price="0" data-stock="0">-- Select Product --</option>
                    {% for p in products %}
                      <option value="{{ p.id }}" data-price="{{ p.selling_price }}" data-stock="{{ p.stock_qty }}" {% if p.stock_qty <= 0 %}disabled{% endif %}>
                        {{ p.name }} (Stock: {{ p.stock_qty }})
                      </option>
                    {% endfor %}
                  </select>
                </td>
                <td><input type="number" step="0.01" name="unit_price[]" class="price-input" readonly value="0.00"></td>
                <td><input type="number" name="quantity[]" class="qty-input" min="1" value="1" required onchange="calculateTotals()" onkeyup="calculateTotals()"></td>
                <td><input type="text" class="subtotal-input" readonly value="0.00"></td>
                <td><button type="button" class="btn btn-danger" onclick="removeRow(this)" style="padding: 0.3rem 0.6rem;">&times;</button></td>
              </tr>
            </tbody>
          </table>

          <div style="margin-top: 1rem; display: flex; justify-content: space-between; align-items: center;">
            <button type="button" class="btn btn-secondary" onclick="addRow()">+ Add Another Item</button>
            <div style="text-align: right;">
              <span style="font-size: 1.1rem; color: var(--muted);">Grand Total:</span>
              <span id="grandTotal" style="font-size: 1.6rem; font-weight: bold; margin-left: 0.5rem; color: var(--primary);">₹0.00</span>
            </div>
          </div>

          <div style="margin-top: 2rem; border-top: 1px solid var(--border); padding-top: 1rem; text-align: right;">
            <button type="submit" class="btn" style="font-size: 1rem; padding: 0.8rem 2rem;">Save & Generate Bill</button>
          </div>
        </form>
      </div>

      <script>
        function updateRow(selectElem) {
          const row = selectElem.closest('.item-row');
          const opt = selectElem.options[selectElem.selectedIndex];
          const price = parseFloat(opt.getAttribute('data-price') || 0);
          const stock = parseInt(opt.getAttribute('data-stock') || 0);
          
          const qtyInput = row.querySelector('.qty-input');
          qtyInput.max = stock;
          row.querySelector('.price-input').value = price.toFixed(2);
          calculateTotals();
        }

        function calculateTotals() {
          let grand = 0;
          document.querySelectorAll('.item-row').forEach(row => {
            const price = parseFloat(row.querySelector('.price-input').value || 0);
            const qty = parseInt(row.querySelector('.qty-input').value || 0);
            const sub = price * qty;
            row.querySelector('.subtotal-input').value = sub.toFixed(2);
            grand += sub;
          });
          document.getElementById('grandTotal').innerText = '₹' + grand.toFixed(2);
        }

        function addRow() {
          const body = document.getElementById('rowsBody');
          const firstRow = body.querySelector('.item-row');
          const clone = firstRow.cloneNode(true);
          clone.querySelectorAll('input').forEach(i => {
            if(i.classList.contains('qty-input')) i.value = 1;
            else i.value = '0.00';
          });
          clone.querySelector('select').selectedIndex = 0;
          body.appendChild(clone);
        }

        function removeRow(btn) {
          const rows = document.querySelectorAll('.item-row');
          if (rows.length > 1) {
            btn.closest('.item-row').remove();
            calculateTotals();
          }
        }
      </script>

    {% elif page == 'inventory' %}
      <div class="card">
        <h2 style="margin-top: 0;">Add / Restock Product</h2>
        <form method="POST" action="{{ url_for('save_product') }}">
          <div class="grid grid-4">
            <div>
              <label>Product Name</label>
              <input type="text" name="name" required placeholder="e.g. Handmade Soap / Perfume">
            </div>
            <div>
              <label>SKU / Barcode</label>
              <input type="text" name="sku" placeholder="RUI-101">
            </div>
            <div>
              <label>Selling Price (₹)</label>
              <input type="number" step="0.01" name="selling_price" required placeholder="0.00">
            </div>
            <div>
              <label>Initial Stock (Units)</label>
              <input type="number" name="stock_qty" min="0" value="10" required>
            </div>
          </div>
          <button type="submit" class="btn" style="margin-top: 1rem;">Save Item</button>
        </form>
      </div>

      <div class="card">
        <h2 style="margin-top: 0;">Stock Register</h2>
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product Name</th>
              <th>Price</th>
              <th>Available Units</th>
              <th>Status</th>
              <th>Update Stock</th>
            </tr>
          </thead>
          <tbody>
            {% for item in products %}
            <tr>
              <td>{{ item.sku or '—' }}</td>
              <td><strong>{{ item.name }}</strong></td>
              <td>₹{{ "%.2f"|format(item.selling_price) }}</td>
              <td>{{ item.stock_qty }}</td>
              <td>
                {% if item.stock_qty > 5 %}
                  <span class="badge badge-ok">In Stock</span>
                {% elif item.stock_qty > 0 %}
                  <span class="badge badge-low">Low Stock</span>
                {% else %}
                  <span class="badge badge-low">Out of Stock</span>
                {% endif %}
              </td>
              <td>
                <form method="POST" action="{{ url_for('adjust_stock') }}" style="display:flex; gap: 0.5rem; align-items:center;">
                  <input type="hidden" name="product_id" value="{{ item.id }}">
                  <input type="number" name="add_qty" placeholder="+Qty" style="width: 75px; padding: 0.25rem 0.5rem;" required>
                  <button type="submit" class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;">Add</button>
                </form>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

    {% elif page == 'history' %}
      <div class="card">
        <h2 style="margin-top: 0;">Sales History</h2>
        <table>
          <thead>
            <tr>
              <th>Invoice #</th>
              <th>Date & Time</th>
              <th>Customer</th>
              <th>Payment</th>
              <th>Amount</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {% for inv in invoices %}
            <tr>
              <td><strong>{{ inv.invoice_no }}</strong></td>
              <td>{{ inv.created_at[:16] }}</td>
              <td>{{ inv.customer_name or 'Walk-in' }}</td>
              <td>{{ inv.payment_mode }}</td>
              <td><strong>₹{{ "%.2f"|format(inv.total_amount) }}</strong></td>
              <td>
                <a href="{{ url_for('invoice_view', inv_id=inv.id) }}" class="btn" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">View & Print</a>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

    {% elif page == 'invoice_view' %}
      <div class="card" style="max-width: 650px; margin: 0 auto; border: 1px dashed #94a3b8; padding: 2rem;">
        <div style="display: flex; justify-content: space-between; border-bottom: 2px solid var(--border); padding-bottom: 1rem;">
          <div>
            <h1 style="margin: 0; font-size: 1.6rem; color: #042f2e;">RUIGANDH</h1>
            <p style="margin: 0.2rem 0; color: var(--muted); font-size: 0.85rem;">Official Tax / Retail Invoice</p>
          </div>
          <div style="text-align: right;">
            <strong style="color: var(--primary);">{{ inv.invoice_no }}</strong>
            <p style="margin: 0.2rem 0; font-size: 0.85rem; color: var(--muted);">Date: {{ inv.created_at[:10] }}</p>
          </div>
        </div>

        <div style="margin: 1.25rem 0; font-size: 0.9rem;">
          <strong>Billed To:</strong> {{ inv.customer_name or 'Walk-in Customer' }}<br>
          {% if inv.customer_phone %}<strong>Phone:</strong> {{ inv.customer_phone }}<br>{% endif %}
          <strong>Payment Mode:</strong> {{ inv.payment_mode }}
        </div>

        <table>
          <thead>
            <tr>
              <th>Description</th>
              <th>Qty</th>
              <th>Rate</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {% for it in items %}
            <tr>
              <td>{{ it.product_name }}</td>
              <td>{{ it.quantity }}</td>
              <td>₹{{ "%.2f"|format(it.unit_price) }}</td>
              <td>₹{{ "%.2f"|format(it.subtotal) }}</td>
            </tr>
            {% endfor %}
            <tr>
              <td colspan="3" style="text-align: right; font-weight: bold; border-top: 2px solid #0f172a; font-size: 1rem;">Total Amount:</td>
              <td style="font-weight: bold; border-top: 2px solid #0f172a; font-size: 1.15rem; color: var(--primary);">₹{{ "%.2f"|format(inv.total_amount) }}</td>
            </tr>
          </tbody>
        </table>

        <p style="text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 2rem;">Thank you for supporting Ruigandh!</p>

        <div class="no-print" style="margin-top: 2rem; display: flex; gap: 1rem; justify-content: space-between;">
          <a href="{{ url_for('pos') }}" class="btn btn-secondary">New Sale</a>
          <div style="display: flex; gap: 0.5rem;">
            {% if whatsapp_url %}
              <a href="{{ whatsapp_url }}" target="_blank" class="btn" style="background: #25d366;">WhatsApp Invoice</a>
            {% endif %}
            <button onclick="window.print()" class="btn">Print / PDF</button>
          </div>
        </div>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""

@app.route('/')
def pos():
    with get_db() as conn:
        products = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
    return render_template_string(BASE_TEMPLATE, page='pos', products=products)

@app.route('/inventory')
def inventory():
    with get_db() as conn:
        products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template_string(BASE_TEMPLATE, page='inventory', products=products)

@app.route('/history')
def sales_history():
    with get_db() as conn:
        invoices = conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    return render_template_string(BASE_TEMPLATE, page='history', invoices=invoices)

@app.route('/save-product', methods=['POST'])
def save_product():
    name = request.form['name'].strip()
    sku = request.form.get('sku', '').strip() or None
    price = float(request.form['selling_price'])
    stock = int(request.form['stock_qty'])

    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO products (name, sku, selling_price, stock_qty) VALUES (?, ?, ?, ?)",
                (name, sku, price, stock)
            )
            flash(f"Item '{name}' added successfully.")
        except sqlite3.IntegrityError:
            flash(f"Error: SKU '{sku}' is already assigned to another product.", "error")
    return redirect(url_for('inventory'))

@app.route('/adjust-stock', methods=['POST'])
def adjust_stock():
    p_id = int(request.form['product_id'])
    add_qty = int(request.form['add_qty'])
    with get_db() as conn:
        conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?", (add_qty, p_id))
    flash("Stock updated successfully.")
    return redirect(url_for('inventory'))

@app.route('/checkout', methods=['POST'])
def checkout():
    cust_name = request.form.get('customer_name', '').strip()
    cust_phone = request.form.get('customer_phone', '').strip()
    pay_mode = request.form.get('payment_mode', 'Cash')

    product_ids = request.form.getlist('item_id[]')
    quantities = request.form.getlist('quantity[]')

    if not product_ids:
        flash("Please select at least one item.", "error")
        return redirect(url_for('pos'))

    with get_db() as conn:
        total_bill = 0
        items_to_save = []

        for p_id, q_str in zip(product_ids, quantities):
            if not p_id:
                continue
            qty = int(q_str)
            prod = conn.execute("SELECT * FROM products WHERE id = ?", (p_id,)).fetchone()
            if not prod or prod['stock_qty'] < qty:
                flash(f"Insufficient stock for {prod['name'] if prod else 'Item'}.", "error")
                return redirect(url_for('pos'))
            
            sub = prod['selling_price'] * qty
            total_bill += sub
            items_to_save.append((prod['id'], prod['name'], prod['selling_price'], qty, sub))

        if not items_to_save:
            flash("No valid line items provided.", "error")
            return redirect(url_for('pos'))

        inv_num = f"RUI-{datetime.now().strftime('%y%m%d%H%M%S')}"
        now = datetime.now().isoformat()

        cur = conn.execute(
            "INSERT INTO invoices (invoice_no, customer_name, customer_phone, total_amount, payment_mode, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (inv_num, cust_name, cust_phone, total_bill, pay_mode, now)
        )
        inv_id = cur.lastrowid

        for it in items_to_save:
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, product_name, unit_price, quantity, subtotal) VALUES (?, ?, ?, ?, ?, ?)",
                (inv_id, it[0], it[1], it[2], it[3], it[4])
            )
            conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?", (it[3], it[0]))

    return redirect(url_for('invoice_view', inv_id=inv_id))

@app.route('/invoice/<int:inv_id>')
def invoice_view(inv_id):
    with get_db() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,)).fetchone()
        items = conn.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (inv_id,)).fetchall()

    whatsapp_url = None
    if inv['customer_phone']:
        clean_phone = ''.join(filter(str.isdigit, inv['customer_phone']))
        if len(clean_phone) == 10:
            clean_phone = "91" + clean_phone
        item_summary = "\\n".join([f"- {it['product_name']} x{it['quantity']}: Rs {it['subtotal']:.2f}" for it in items])
        text = f"Hello {inv['customer_name'] or 'Valued Customer'}, thank you for shopping at Ruigandh!\\n\\n*Invoice:* {inv['invoice_no']}\\n{item_summary}\\n\\n*Total Paid:* Rs {inv['total_amount']:.2f}\\nMode: {inv['payment_mode']}"
        whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(text)}"

    return render_template_string(BASE_TEMPLATE, page='invoice_view', inv=inv, items=items, whatsapp_url=whatsapp_url)

if __name__ == '__main__':
    print("Ruigandh app running locally at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)