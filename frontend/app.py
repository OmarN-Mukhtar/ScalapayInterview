from pathlib import Path
import sqlite3
import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_plotly_events import plotly_events


db_path = "eu_regulatory_data.db"

SCALAPAY_BG = "#FBE8E9"

SCALAPAY_COLORS = [
    "#F7CBCF",
    "#8994F5",
    "#64CBF9",
    "#F4D84E",
    "#000000",
]

URGENCY_COLORS = {
    "high": "#E84855",
    "medium": "#F4A340",
    "low": "#3CB371",
    "unknown": "#9CA3AF",
}

st.set_page_config(
    page_title="Regulatory Monitoring Dashboard",
    page_icon="⚖️",
    layout="wide",
)

st.markdown(
    f"""
    <style>
    .stApp {{
        background: {SCALAPAY_BG};
    }}

    [data-testid="stMetric"] {{
        background: #FFFFFF;
        border: 1px solid #F7CBCF;
        border-radius: 16px;
        padding: 16px;
    }}

    iframe {{
        background: {SCALAPAY_BG} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Loading regulatory database...")
def load_data(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        id,
        title,
        source,
        published_date,
        status,
        type,
        summary,
        url,
        refined_category AS impact_area,
        relevance,
        urgency,
        urgency_level,
        score,
        deadline_date
    FROM com_consultations

    UNION ALL

    SELECT
        id,
        title,
        source,
        published_date,
        status,
        type,
        summary,
        url,
        refined_category AS impact_area,
        relevance,
        urgency,
        urgency_level,
        score,
        NULL AS deadline_date
    FROM com_proposals

    UNION ALL

    SELECT
        id,
        title,
        source,
        published_date,
        status,
        type,
        summary,
        url,
        refined_category AS impact_area,
        relevance,
        urgency,
        urgency_level,
        score,
        NULL AS deadline_date
    FROM eba_guidelines

    UNION ALL

    SELECT
        id,
        title,
        source,
        published_date,
        status,
        type,
        summary,
        url,
        refined_category AS impact_area,
        relevance,
        urgency,
        urgency_level,
        score,
        NULL AS deadline_date
    FROM eba_rts
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
    df["deadline_date"] = pd.to_datetime(df["deadline_date"], errors="coerce")

    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
    df["relevance"] = pd.to_numeric(df["relevance"], errors="coerce").fillna(0)
    df["urgency"] = pd.to_numeric(df["urgency"], errors="coerce").fillna(0)

    df["type"] = df["type"].fillna("Unknown")
    df["urgency_level"] = df["urgency_level"].fillna("unknown").str.lower()
    df["impact_area"] = df["impact_area"].fillna("Unclassified")
    df["summary"] = df["summary"].fillna("No summary available.")
    df["source"] = df["source"].fillna("Unknown")
    df["status"] = df["status"].fillna("Unknown")
    df["title"] = df["title"].fillna("Untitled item")

    return df.sort_values(["score", "published_date"], ascending=[False, False])


def navigate(mode: str, value: str | None = None) -> None:
    st.session_state["mode"] = mode
    st.session_state["value"] = value
    st.rerun()


def current_view() -> tuple[str, str | None]:
    if "mode" not in st.session_state:
        st.session_state["mode"] = "home"
        st.session_state["value"] = None

    return st.session_state["mode"], st.session_state["value"]


def wrap_label(value: str, width: int = 16) -> str:
    return "<br>".join(textwrap.wrap(str(value), width=width))


def donut_colors(labels: list[str], label_col: str) -> list[str]:
    if label_col == "urgency_level":
        return [URGENCY_COLORS.get(label.lower(), "#9CA3AF") for label in labels]

    return [SCALAPAY_COLORS[i % len(SCALAPAY_COLORS)] for i in range(len(labels))]


def make_donut(
    counts: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
):
    counts = counts.copy()
    counts["_count"] = pd.to_numeric(counts[value_col], errors="coerce").fillna(0).astype(int)

    labels = counts[label_col].astype(str).tolist()
    values = counts["_count"].tolist()
    wrapped_labels = [wrap_label(label) for label in labels]
    custom_data = list(zip(labels, wrapped_labels, values))

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            sort=False,
            domain=dict(x=[0.02, 0.98], y=[0.06, 0.92]),
            marker=dict(
                colors=donut_colors(labels, label_col),
                line=dict(width=0),
            ),
            customdata=custom_data,
            textposition="inside",
            texttemplate="%{customdata[1]}<br>%{customdata[2]}",
            hovertemplate="%{label}<br>%{value} items<extra></extra>",
            insidetextorientation="tangential",
        )
    )

    fig.update_layout(
        title=dict(text=title, x=0.5, y=0.96),
        showlegend=False,
        margin=dict(t=0, b=0, l=0, r=0),
        height=470,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        paper_bgcolor=SCALAPAY_BG,
        plot_bgcolor=SCALAPAY_BG,
        font=dict(color="#2B2B2B"),
        clickmode="event+select",
    )

    return fig


def render_clickable_donut(
    counts: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    mode: str,
    key: str,
) -> None:
    fig = make_donut(counts, label_col, value_col, title)

    clicked = plotly_events(
        fig,
        click_event=True,
        hover_event=False,
        select_event=False,
        override_height=470,
        override_width="100%",
        key=key,
)
    if clicked:
        point = clicked[0]
        selected_label = point.get("label")

        if selected_label is None and "customdata" in point:
            selected_label = point["customdata"][0]

        if selected_label is None and "pointNumber" in point:
            selected_label = counts.iloc[int(point["pointNumber"])][label_col]

        if selected_label is None and "pointIndex" in point:
            selected_label = counts.iloc[int(point["pointIndex"])][label_col]

        if selected_label:
            navigate(mode, str(selected_label))

    st.caption("Click a ring segment to open the filtered database view.")


def render_home(df: pd.DataFrame) -> None:
    st.title("⚖️ Regulatory Monitoring Dashboard")
    st.write(
        "A compact view of monitored regulatory items, grouped by document type and urgency."
    )

    top1, top2, top3 = st.columns(3)

    top1.metric("Total items", len(df))
    top2.metric("High urgency", int((df["urgency_level"] == "high").sum()))
    top3.metric("Sources", df["source"].nunique())

    st.divider()

    left, right = st.columns(2)

    type_counts = (
        df.groupby("type", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    urgency_counts = (
        df.groupby("urgency_level", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    with left:
        render_clickable_donut(
            type_counts,
            label_col="type",
            value_col="count",
            title="Items by type",
            mode="type",
            key="type_donut",
        )

    with right:
        render_clickable_donut(
            urgency_counts,
            label_col="urgency_level",
            value_col="count",
            title="Items by urgency",
            mode="urgency_level",
            key="urgency_donut",
        )


def filter_df(
    df: pd.DataFrame,
    mode: str,
    value: str | None,
) -> pd.DataFrame:
    if mode == "type" and value:
        return df[df["type"] == value]

    if mode == "urgency_level" and value:
        return df[df["urgency_level"] == value]

    if mode == "source" and value:
        return df[df["source"] == value]

    return df


def render_database(
    df: pd.DataFrame,
    mode: str,
    value: str | None,
) -> None:
    filtered = filter_df(df, mode, value)

    c1, c2, c3 = st.columns([1, 1, 4])

    with c1:
        if st.button(
            "← Home",
            use_container_width=True,
            key="database_home_button",
        ):
            navigate("home", None)

    with c2:
        if st.button(
            "Whole database",
            use_container_width=True,
            key="database_whole_database_button",
        ):
            navigate("all", None)

    if mode == "type":
        st.title(f"Database: {value}")
        st.caption(f"Showing all regulatory items with type = {value}")
    elif mode == "urgency_level":
        st.title(f"Database: {value.title()} urgency")
        st.caption(f"Showing all regulatory items with urgency level = {value}")
    elif mode == "source":
        st.title(f"Source: {value}")
        st.caption(f"Showing all regulatory items from {value}")
    else:
        st.title("Full regulatory database")
        st.caption("Showing all monitored regulatory items.")

    st.metric("Items shown", len(filtered))

    st.divider()

    search = st.text_input(
        "Search title, summary or impact area",
        placeholder="Example: payment services, AML, DORA, consumer credit",
        key="database_search_input",
    )

    if search:
        mask = (
            filtered["title"].str.contains(search, case=False, na=False)
            | filtered["summary"].str.contains(search, case=False, na=False)
            | filtered["impact_area"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    display_cols = [
        "title",
        "source",
        "published_date",
        "status",
        "type",
        "impact_area",
        "urgency_level",
        "score",
        "deadline_date",
        "summary",
        "url",
    ]

    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "title": st.column_config.TextColumn("Title", width="large"),
            "source": "Source",
            "published_date": st.column_config.DateColumn("Published"),
            "deadline_date": st.column_config.DateColumn("Deadline"),
            "urgency_level": "Urgency",
            "impact_area": "Impact area",
            "summary": st.column_config.TextColumn("Summary", width="large"),
            "score": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%.0f",
            ),
            "url": st.column_config.LinkColumn(
                "Source link",
                display_text="Open",
            ),
        },
    )


def main() -> None:
    df = load_data(db_path)
    mode, value = current_view()

    with st.sidebar:
        st.header("Navigation")

        if st.button(
            "Home",
            use_container_width=True,
            key="sidebar_home_button",
        ):
            navigate("home", None)

        if st.button(
            "Whole database",
            use_container_width=True,
            key="sidebar_whole_database_button",
        ):
            navigate("all", None)

        st.divider()
        st.subheader("Sources")

        source_counts = df["source"].value_counts().sort_index()

        for index, (source, count) in enumerate(source_counts.items()):
            if st.button(
                f"{source} ({count})",
                use_container_width=True,
                key=f"sidebar_source_{index}",
            ):
                navigate("source", source)

        st.divider()
        st.subheader("Types")

        type_counts = df["type"].value_counts().sort_index()

        for index, (item_type, count) in enumerate(type_counts.items()):
            if st.button(
                f"{item_type} ({count})",
                use_container_width=True,
                key=f"sidebar_type_{index}",
            ):
                navigate("type", item_type)

        st.divider()
        st.caption(f"Database: `{Path(db_path).name}`")

    if mode == "home":
        render_home(df)
    else:
        render_database(df, mode, value)


if __name__ == "__main__":
    main()