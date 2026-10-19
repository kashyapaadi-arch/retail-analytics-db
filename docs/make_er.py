"""Generate the core retail ER diagram as SVG and PNG with Graphviz."""

from pathlib import Path

from graphviz import Digraph


OUT = Path(__file__).resolve().parent


def build_graph() -> Digraph:
    graph = Digraph("retail_core", format="svg")
    graph.attr(
        rankdir="LR",
        bgcolor="white",
        pad="0.25",
        nodesep="0.42",
        ranksep="0.9",
        splines="polyline",
        fontname="Segoe UI",
        label="Sales and Inventory Analytics Database — Core ERD",
        labelloc="t",
        fontsize="20",
    )
    graph.attr("node", shape="plain", fontname="Segoe UI")
    graph.attr("edge", dir="both", arrowtail="tee", arrowhead="crow", color="#52708b", penwidth="1.2")

    entities = {
        "category": ["PK category_id", "UQ name"],
        "product": ["PK product_id", "FK category_id", "unit_price", "cost_price", "reorder_level"],
        "inventory": ["PK/FK product_id", "quantity_in_stock", "last_updated"],
        "supplier": ["PK supplier_id", "name", "contact", "city"],
        "supplier_product": ["PK/FK supplier_id", "PK/FK product_id", "supply_price"],
        "customer": ["PK customer_id", "UQ phone", "name", "city", "join_date"],
        "employee": ["PK employee_id", "name", "role", "hire_date"],
        "purchase_order": ["PK po_id", "FK supplier_id", "order_date", "status"],
        "purchase_order_item": ["PK/FK po_id", "PK/FK product_id", "quantity", "unit_cost"],
        "sales_order": ["PK order_id", "FK customer_id", "FK employee_id", "order_date", "payment_mode", "total_amount"],
        "order_item": ["PK/FK order_id", "PK/FK product_id", "quantity", "unit_price", "discount_pct"],
    }
    for table, fields in entities.items():
        rows = "".join(
            f'<TR><TD ALIGN="LEFT" CELLPADDING="4"><FONT COLOR="#52677b">{field}</FONT></TD></TR>'
            for field in fields
        )
        graph.node(
            table,
            f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" COLOR="#b8c7d6" '
            f'BGCOLOR="white"><TR><TD BGCOLOR="#e8f1f8" CELLPADDING="6">'
            f'<B>{table}</B></TD></TR>{rows}</TABLE>>',
        )

    for child, parent in [
        ("product", "category"),
        ("inventory", "product"),
        ("supplier_product", "supplier"),
        ("supplier_product", "product"),
        ("purchase_order", "supplier"),
        ("purchase_order_item", "purchase_order"),
        ("purchase_order_item", "product"),
        ("sales_order", "customer"),
        ("sales_order", "employee"),
        ("order_item", "sales_order"),
        ("order_item", "product"),
    ]:
        graph.edge(parent, child, taillabel="1", headlabel="0..*", labeldistance="1.7", fontsize="9")
    return graph


def main() -> None:
    graph = build_graph()
    graph.render(filename="er_diagram", directory=str(OUT), cleanup=True, format="svg")
    graph.format = "png"
    graph.render(filename="er_diagram", directory=str(OUT), cleanup=True, format="png")
    print(f"Generated {OUT / 'er_diagram.svg'} and {OUT / 'er_diagram.png'}")


if __name__ == "__main__":
    main()

