# graph_db.py
from neo4j import GraphDatabase
import streamlit as st
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
from collections import defaultdict
import re


class Neo4jConnection:
    """Handles connection and all graph database operations for Neo4j."""

    def __init__(self, uri, user, password, database="neo4j"):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            print(f"✅ Connected to Neo4j (db: {self.database})")
        except Exception as e:
            st.error(f"Failed to create Neo4j driver: {e}")

    def close(self):
        """ close the connection of the neo4j database"""
        if self.driver is not None:
            self.driver.close()

    def execute_write(self, query, parameters=None):
        """Create a session with the database for executing write queries"""
        with self.driver.session(database=self.database) as session:
            """Execute the provided write query within the session
            The lambda function is passed to the session to run the query
             with the given parameters"""
            session.execute_write(lambda tx: tx.run(query, parameters))

    def execute_read(self, query, parameters=None):
        """Create a session with the database for executing read queries"""
        with self.driver.session(database=self.database) as session:
            """ Execute the provided read query within the session and 
             fetch the result
             The lambda function is passed to the session to run the 
             query with the given parameters"""
            result = session.execute_read(lambda tx: \
                                          list(tx.run(query, parameters)))
            """Convert result into a list of dict for easier access to data
            Each record is a dictionary where keys are column names and
             values are the respective values"""
            return [dict(record) for record in result]


    def add_triples(self, triples):
        """ add the nodes and relations to the database """
        grouped_triples = defaultdict(list)
        for e1, rel, e2 in triples:
            sanitized_rel = re.sub(r"[^a-zA-Z0-9_]", "", \
                                   rel.replace(" ", "_")).upper()
            if sanitized_rel:
                grouped_triples[sanitized_rel].append([e1, e2])

        for rel_type, pairs in grouped_triples.items():
            query = f"""
            UNWIND $pairs as pair
            MERGE (e1:Entity {{name: pair[0]}})
            MERGE (e2:Entity {{name: pair[1]}})
            MERGE (e1)-[:`{rel_type}`]->(e2)
            """
            self.execute_write(query, {"pairs": pairs})

    """Retrieves the node labels and relationship 
    types from the database schema."""
    def get_schema(self):
        labels_query = "CALL db.labels() YIELD label"
        labels = [item["label"] for item in self.execute_read(labels_query)]

        rels_query = "CALL db.relationshipTypes() YIELD relationshipType"
        rel_types = [item["relationshipType"] \
                     for item in self.execute_read(rels_query)]

        return {"node_labels": labels, "relationship_types": rel_types}

    def generate_cypher(self, question: str, model):
        """takes input of user query and model, returns with cypher query"""
        schema = self.get_schema()

        prompt = f"""
        You are a Neo4j Cypher expert. Convert the user's natural language 
        question into a single Cypher query
        using ONLY the provided graph schema. Return only the Cypher query,
         no explanation.

        **Graph Schema:**
        - Node labels: {schema['node_labels']}
        - Relationship types: {schema['relationship_types']}

        **Rules:**
        1. Always match nodes by performing case-insensitive search on the 
            'name' property using toLower().
        2. Only use the node labels and relationship types from the schema.
        3. Never use write operations (CREATE, SET, DELETE, MERGE). 
            Only read queries.
        4. The primary node label is 'Entity', and all nodes have 
            a 'name' property.
        5. Prefer queries that include both:
           - The matching node(s), and
           - Their directly connected neighbors and relationships.

        
        Question: {question}                        
        """

        try:
            cypher_query = model.generate(prompt).strip()

            if "```" in cypher_query:
                cypher_query = cypher_query.split("```")[1].\
                    strip("cypher\n").strip()

            """in case if the cypher query has the commands that might 
            modify the database, we will not allow that to pass """
            if any(
                op in cypher_query.upper()
                for op in ["CREATE", "SET", "DELETE", "MERGE"]
            ):
                raise ValueError("❌ Disallowed write operation in query.")

            return cypher_query
        except Exception as e:
            st.error(f"Error generating Cypher query: {e}")
            return None

    def search_graph(self, query_text, model):
        """search the graph and export the nodes and relationships using LLM"""
        # 1. Ask the LLM to extract entities
        entity_prompt = f"""
        Extract all key entities (people, organizations, locations) 
        from the following question. 
        Return them as a simple comma-separated list.
        
        Question: {query_text}
        """
        entity_string = model.generate(entity_prompt)

        # 2. Clean the LLM's output
        entities = [e.strip() for e in entity_string.split(",") if e.strip()]

        if not entities:
            return []

        # 3. The query remains the same
        cypher_query = """
        UNWIND $entities as entityName
        MATCH (n:Entity)-[r]-(m)
        WHERE toLower(n.name) CONTAINS toLower(entityName)
        RETURN n.name as node, type(r) as relationship, m.name as target
        LIMIT 25
        """
        return self.execute_read(cypher_query, parameters={"entities": entities})

    def check_if_graph_exists(self):
        query = "MATCH (n) RETURN n LIMIT 1"
        result = self.execute_read(query)
        return len(result) > 0

    def visualize_subgraph(self, query_text, st_object, model):
        """Visualize graph using st-link-analysis"""
        raw_data = self.search_graph(query_text, model)
        if not raw_data:
            st_object.warning("No visual data to display for this query.")
            return

        #  Build node/edge lists
        nodes = []
        edges = []
        node_ids = set()
        edge_ids = set()
        node_labels = set()
        edge_labels = set()

        # Pre-collect names
        node_name_map = {}

        for row in raw_data:
            src = row.get("node")
            rel = row.get("relationship", "RELATED_TO")
            tgt = row.get("target")

            if not src or not tgt:
                continue

            # Handle nodes
            for n in [src, tgt]:
                if n not in node_ids:
                    node_data = {"id": n, "label": "Entity", "name": n}
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
                    "destination_name": tgt,
                }
                edges.append({"data": edge_data})
                edge_ids.add(edge_id)
                edge_labels.add(rel)

        #  Node & Edge styles
        node_styles = []
        for i, label in enumerate(node_labels):
            style = NodeStyle(label, "yellow", "name", "database")
            node_styles.append(style)

        edge_styles = [
            EdgeStyle(label, caption="label", directed=True) for label in edge_labels
        ]

        elements = {"nodes": nodes, "edges": edges}

        st_link_analysis(elements, "cose", node_styles, edge_styles, height=600)
