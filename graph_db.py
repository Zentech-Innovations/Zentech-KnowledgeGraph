# graph_db.py
from neo4j import GraphDatabase
import streamlit as st
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
import random
import spacy
from collections import defaultdict
import re

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'...")
    from spacy.cli import download

    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


class Neo4jConnection:
    """Handles connection and all graph database operations for Neo4j."""

    def __init__(self, uri, user, password, database="neo4j"):
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = None
        try:
            self._driver = GraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            )
            print(f"✅ Connected to Neo4j (db: {self._database})")
        except Exception as e:
            st.error(f"Failed to create Neo4j driver: {e}")

    def close(self):
        if self._driver is not None:
            self._driver.close()

    def _execute_write(self, query, parameters=None):
        with self._driver.session(database=self._database) as session:
            session.write_transaction(lambda tx: tx.run(query, parameters))

    def _execute_read(self, query, parameters=None):
        with self._driver.session(database=self._database) as session:
            result = session.read_transaction(
                lambda tx: list(tx.run(query, parameters))
            )
            return [dict(record) for record in result]

    def clear_database(self):
        query = "MATCH (n) DETACH DELETE n"
        self._execute_write(query)
        print(f"🧹 Database '{self._database}' cleared.")

    def add_triples(self, triples):
        grouped_triples = defaultdict(list)
        for e1, rel, e2 in triples:
            sanitized_rel = re.sub(r"[^a-zA-Z0-9_]", "", rel.replace(" ", "_")).upper()
            if sanitized_rel:
                grouped_triples[sanitized_rel].append([e1, e2])

        for rel_type, pairs in grouped_triples.items():
            query = f"""
            UNWIND $pairs as pair
            MERGE (e1:Entity {{name: pair[0]}})
            MERGE (e2:Entity {{name: pair[1]}})
            MERGE (e1)-[:`{rel_type}`]->(e2)
            """
            self._execute_write(query, {"pairs": pairs})

    def get_schema(self):
        labels_query = "CALL db.labels() YIELD label"
        labels = [item["label"] for item in self._execute_read(labels_query)]

        rels_query = "CALL db.relationshipTypes() YIELD relationshipType"
        rel_types = [
            item["relationshipType"] for item in self._execute_read(rels_query)
        ]

        return {"node_labels": labels, "relationship_types": rel_types}

    def generate_cypher(self, question: str, model):
        schema = self.get_schema()

        prompt = f"""
        You are a Neo4j Cypher expert. Convert the user's natural language question into a single Cypher query
        using ONLY the provided graph schema. Return only the Cypher query, no explanation.

        **Graph Schema:**
        - Node labels: {schema['node_labels']}
        - Relationship types: {schema['relationship_types']}

        **Rules:**
        1. Always match nodes by performing case-insensitive search on the 'name' property using toLower().
        2. Only use the node labels and relationship types from the schema.
        3. Never use write operations (CREATE, SET, DELETE, MERGE). Only read queries.
        4. The primary node label is 'Entity', and all nodes have a 'name' property.
        5. Prefer queries that include both:
           - The matching node(s), and
           - Their directly connected neighbors and relationships.

        ---
        Question: {question}
        """

        try:
            cypher_query = model.generate(prompt).strip()

            if "```" in cypher_query:
                cypher_query = cypher_query.split("```")[1].strip("cypher\n").strip()

            if any(
                op in cypher_query.upper()
                for op in ["CREATE", "SET", "DELETE", "MERGE"]
            ):
                raise ValueError("❌ Disallowed write operation in query.")

            return cypher_query
        except Exception as e:
            st.error(f"Error generating Cypher query: {e}")
            return None

    def search_graph(self, query_text):
        doc = nlp(query_text)
        entities = {ent.text.strip() for ent in doc.ents}
        for token in doc:
            if token.pos_ == "PROPN" and not any(
                ent.start <= token.i < ent.end for ent in doc.ents
            ):
                entities.add(token.text.strip())

        if not entities:
            return []

        cypher_query = """
        UNWIND $entities as entityName
        MATCH (n:Entity)-[r]-(m)
        WHERE toLower(n.name) CONTAINS toLower(entityName)
        RETURN n.name as node, type(r) as relationship, m.name as target
        LIMIT 25
        """
        return self._execute_read(cypher_query, parameters={"entities": list(entities)})

    def check_if_graph_exists(self):
        query = "MATCH (n) RETURN n LIMIT 1"
        result = self._execute_read(query)
        return len(result) > 0


    def visualize_subgraph(self, query_text, st_object, model):
        """Visualize graph using st-link-analysis instead of streamlit-agraph."""
        raw_data = self.search_graph(query_text)
        if not raw_data:
            st_object.warning("No visual data to display for this query.")
            return

        # --- Build node/edge lists ---
        nodes = []
        edges = []
        node_ids = set()
        edge_ids = set()
        node_labels = set()
        edge_labels = set()

        # Pre-collect names
        node_name_map = {}

        # Assign colors
        colors = [
            '#FF7F3E', '#2A629A', '#B93160', '#6EBF8B', '#FFD700',
            '#4682B4', '#D2691E', '#9ACD32', '#FF69B4', '#00CED1'
        ]
        random.shuffle(colors)

        for row in raw_data:
            src = row.get("node")
            rel = row.get("relationship", "RELATED_TO")
            tgt = row.get("target")

            if not src or not tgt:
                continue

            # Handle nodes
            for n in [src, tgt]:
                if n not in node_ids:
                    node_data = {
                        "id": n,
                        "label": "Entity",
                        "name": n
                    }
                    nodes.append({"data": node_data})
                    node_ids.add(n)
                    node_labels.add("Entity")
                    node_name_map[n] = n

            # Handle edges
            edge_id = f"{src}-{rel}-{tgt}"
            if edge_id not in edge_ids:
                edge_data = {
                    "id": edge_id,
                    "source": src,
                    "target": tgt,
                    "label": rel,
                    "source_name": src,
                    "destination_name": tgt
                }
                edges.append({"data": edge_data})
                edge_ids.add(edge_id)
                edge_labels.add(rel)

        # --- Node & Edge styles ---
        node_styles = []
        for i, label in enumerate(node_labels):
            style = NodeStyle(
                label,
                colors[i % len(colors)],
                'name',  # caption property
                'database'
            )
            node_styles.append(style)

        edge_styles = [
            EdgeStyle(label, caption='label', directed=True) for label in edge_labels
        ]

        elements = {"nodes": nodes, "edges": edges}

        st_link_analysis(elements, "cose", node_styles, edge_styles, height=600)

