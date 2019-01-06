from flask import Blueprint
from bokeh.models import HoverTool, FactorRange, LinearAxis, Grid, Range1d
from bokeh.models.glyphs import VBar
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models.sources import ColumnDataSource
from flask import render_template, request, redirect, url_for
from tables import Energy, Gas
from tools.global_paths import MONTHS_NAMES_FILE, BUILDINGS_NAMES_POLISH_FILE, BUILDINGS_CODE_FILE
import json
from database import db

bp = Blueprint('energy', __name__, url_prefix='')


@bp.route('/add/energy', methods=['GET', 'POST'])
def add_energy():
    type_choice = get_energy_type(current_page="energy")
    if request.method == 'POST':
        if "data_input" in request.form:
            date = request.form.get('date')
            year, month = date.split('-')[:2]
            quantity = request.form.get('quantity')
            consumption_price = request.form.get('consumption_price')
            transmission_price = request.form.get('transmission_price')

            db.session.add(Energy(year=year, month=month, quantity=quantity,
                                  consumption_price=consumption_price, transmission_price=transmission_price,
                                  building='SCH'))

            db.session.commit()
    if type_choice == 'energy':
        return render_template("add_energy.html", rows=get_data(type_choice="energy"))
    else:
        return redirect(url_for("energy.add_gas"))


@bp.route('/add/gas', methods=['GET', 'POST'])
def add_gas():
    type_choice = get_energy_type(current_page="gas")
    if request.method == 'POST':

        if "data_input" in request.form:
            date = request.form.get('date')
            year, month = date.split('-')[:2]
            quantity = request.form.get('quantity')
            price = request.form.get('price')

            db.session.add(Gas(year=year, month=month, quantity=quantity,
                               price=price, building='WOR'))
            db.session.commit()

    if type_choice == 'gas':
        return render_template("add_gas.html", rows=get_data(type_choice="gas"))
    else:
        return redirect(url_for("energy.add_energy"))


def get_energy_type(current_page):
    type_choice = current_page
    if request.method == "POST" and "energy_type" in request.form:
        type_choice = request.form["options"]
    return type_choice


def get_data(type_choice):
    with open(MONTHS_NAMES_FILE) as f:
        months_names_mapping = json.loads(f.read())

    with open(BUILDINGS_NAMES_POLISH_FILE) as f:
        buildings_names = json.loads(f.read())

    if type_choice == 'energy':
        rows = Energy.query.order_by(Energy.year.desc(), Energy.month.desc()).limit(10).all()
        data = [[row.year, months_names_mapping[str(row.month)], buildings_names[row.building],
                 row.quantity, row.consumption_price, row.transmission_price] for row in rows]
    elif type_choice == 'gas':
        rows = Gas.query.order_by(Gas.year.desc(), Gas.month.desc()).limit(10).all()
        data = [[row.year, months_names_mapping[str(row.month)], buildings_names[row.building],
                 row.quantity, row.price] for row in rows]
    return data


@bp.route('/gas')
def gas():
    return redirect(url_for('energy.energy'))


@bp.route('/show', methods=['GET', 'POST'])
def energy():
    building_name = request.form.get('comp_select')
    year = request.form.get('year_select') if request.form.get('year_select') is not None else 2017

    if building_name is not None and year is not None:
        plot = get_data_to_chart(building_name, year)
    else:
        plot = get_data_to_chart('school', 2017)
        building_name = 'school'
    script, div = components(plot)
    return render_template("energy.html", year=year,
                           the_div=div, the_script=script,
                           building='szkoła' if building_name == 'school' else 'warsztat')


def get_data_to_chart(building_name: str, year: int):
    names = {'school': Energy, 'workshop': Energy}
    building = names[building_name]
    with open(MONTHS_NAMES_FILE) as f:
        months_names_mapping = json.loads(f.read())

    month, quantity, price = [], [], []
    with open(BUILDINGS_CODE_FILE) as f:
        buildings_codes = json.loads(f.read())
    for row in building.query.filter_by(year=year, building=buildings_codes[building_name]).all():
        month.append(months_names_mapping[str(row.month)])
        quantity.append(row.quantity)
        price.append((row.consumption_price if row.consumption_price is not None else 0 +
                                                                                      (
                                                                                          row.transmission_price if row.transmission_price is not None else 0)))
    data = {"month": month, "quantity": quantity, "price": price}
    hover = create_hover_tool()
    plot = create_bar_chart(data, "Zużycie energii", "month",
                            "quantity", hover)
    return plot


def create_hover_tool():
    """Generates the HTML for the Bokeh's hover data tool on our graph."""
    hover_html = """
      <div>
        <span class="hover-tooltip">$x</span>
      </div>
      <div>
        <span class="hover-tooltip">Zużycie: @quantity kWh</span>
      </div>
      <div>
        <span class="hover-tooltip">Koszt: @price{0.00} zł</span>
      </div>
    """
    return HoverTool(tooltips=hover_html)


def create_bar_chart(data, title, x_name, y_name, hover_tool=None,
                     width=1200, height=600):
    """Creates a bar chart plot with the exact styling for the centcom
       dashboard. Pass in data as a dictionary, desired plot title,
       name of x axis, y axis and the hover tool HTML.
    """
    source = ColumnDataSource(data)
    xdr = FactorRange(factors=data[x_name])
    ydr = Range1d(start=0, end=max(data[y_name]) * 1.5)

    tools = []
    if hover_tool:
        tools = [hover_tool, ]

    plot = figure(title=title, x_range=xdr, y_range=ydr, plot_width=width,
                  plot_height=height, h_symmetry=False, v_symmetry=False,
                  min_border=0, toolbar_location="above", tools=tools,
                  responsive=True, outline_line_color="#666666")

    glyph = VBar(x=x_name, top=y_name, bottom=0, width=.8,
                 fill_color="#e12127")
    plot.add_glyph(source, glyph)

    xaxis = LinearAxis()
    yaxis = LinearAxis()

    plot.add_layout(Grid(dimension=0, ticker=xaxis.ticker))
    plot.add_layout(Grid(dimension=1, ticker=yaxis.ticker))
    plot.toolbar.logo = None
    plot.min_border_top = 0
    plot.xgrid.grid_line_color = None
    plot.ygrid.grid_line_color = "#999999"
    plot.yaxis.axis_label = "Zużycie energii elektrycznej [kWh]"
    plot.ygrid.grid_line_alpha = 0.1
    plot.xaxis.axis_label = "Miesiąc"
    plot.xaxis.major_label_orientation = 1
    return plot