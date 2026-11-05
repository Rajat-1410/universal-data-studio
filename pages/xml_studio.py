"""
Universal XML Studio & Multi-Format Converter (Phase 5)
Interactive XML editor with hierarchical search, tag/attribute editing, syntax validation,
tag renaming, Excel-to-XML custom schema mapping, and cross-format conversions.
"""
import io
import json
import re
import streamlit as st
import pandas as pd
from xml.dom import minidom

from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_metric_card,
    render_active_file_banner,
)
from utils.session_manager import SessionManager
from core.xml_engine import UniversalXmlEditor, UniversalFormatConverter
from core.file_reader import XmlReader
from config import SAMPLES_DIR


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Universal XML Studio & Converter",
        description="Search, inspect, and edit hierarchical XML documents, map Excel to XML schemas, and convert file formats seamlessly.",
        badge="Phase 5 Active",
    )

    active_file = render_active_file_banner()
    files = st.session_state.get("files", {})

    # Discovered XML files in session
    xml_files = {fid: f for fid, f in files.items() if f["format"] == "xml"}

    tab_inspect, tab_edit, tab_map, tab_convert = st.tabs([
        "🌲 XML Inspector & Search",
        "✏️ Interactive XML Editor",
        "🗺️ Excel to XML Schema Mapper",
        "🔄 Universal Cross-Converter",
    ])

    # =============================================================
    # TAB 1: XML INSPECTOR & SEARCH
    # =============================================================
    with tab_inspect:
        st.markdown("##### 🌲 XML Hierarchy & Node Search")

        if not xml_files:
            st.info("No XML document currently active in memory.")
            if st.button("📥 Load Sample ERP Transaction XML (sample_data.xml)", key="btn_load_sample_xml_inspect"):
                xml_sample_p = SAMPLES_DIR / "sample_data.xml"
                if xml_sample_p.exists():
                    with open(xml_sample_p, "rb") as xf:
                        SessionManager.add_uploaded_file("sample_data.xml", xf.read())
                    st.success("Loaded sample_data.xml!")
                    st.rerun()
            curr_xml_str = ""
        else:
            selected_xml_fid = st.selectbox(
                "Select XML document:",
                options=list(xml_files.keys()),
                format_func=lambda x: xml_files[x]["filename"],
                key="xml_inspect_doc_sel",
            )
            raw_bytes = xml_files[selected_xml_fid]["raw_bytes"]
            try:
                from modules.tally.tally_reader import TallyReader
                curr_xml_str = TallyReader.decode_and_sanitize_xml(raw_bytes)[1]
            except Exception:
                curr_xml_str = raw_bytes.decode("utf-8", errors="replace")

        if curr_xml_str:
            is_valid, err_msg = UniversalXmlEditor.validate_xml_syntax(curr_xml_str)
            if is_valid:
                st.caption("✅ XML Syntax: **Well-formed and valid**")
            else:
                st.error(f"❌ XML Syntax Warning: {err_msg}")

            # Deep Structural Metrics
            try:
                struct_summary = UniversalXmlEditor.get_xml_structural_summary(curr_xml_str)
                m1, m2, m3, m4 = st.columns(4)
                render_metric_card("Root Element", f"<{struct_summary['root_tag']}>", "Top-level tag", col=m1, color="#60A5FA")
                render_metric_card("Total Elements", str(struct_summary["total_elements"]), "Node count", col=m2, color="#34D399")
                render_metric_card("Unique Tags", str(struct_summary["unique_tags"]), "Distinct elements", col=m3, color="#F59E0B")
                render_metric_card("Max Depth", str(struct_summary["max_depth"]), "Hierarchy levels", col=m4, color="#818CF8")

                with st.expander("📊 Tag Hierarchy & Repeated Elements Summary", expanded=True):
                    st.dataframe(pd.DataFrame(struct_summary["tags_summary"]), use_container_width=True)
            except Exception as se:
                st.warning(f"Could not calculate structural breakdown: {str(se)}")

            # Search nodes
            st.markdown("###### 🔍 Search Nodes in Document")
            s_c1, s_c2 = st.columns([2, 1])
            with s_c1:
                search_q = st.text_input("Search Query:", placeholder="Type tag name, text value, or attribute...", key="xml_node_search_q")
            with s_c2:
                search_by_mode = st.selectbox("Search By:", ["tag", "text", "attribute"], key="xml_search_by_mode")

            matched_nodes = UniversalXmlEditor.search_nodes(curr_xml_str, search_q, search_by=search_by_mode)
            st.caption(f"Found **{len(matched_nodes)}** matching node(s):")

            if matched_nodes:
                st.dataframe(pd.DataFrame(matched_nodes), use_container_width=True)

            with st.expander("📄 View Formatted XML Snippet", expanded=False):
                beautify = st.checkbox("Format / Indent XML", value=True, key="chk_beautify_inspect")
                display_text = curr_xml_str
                if beautify:
                    try:
                        display_text = minidom.parseString(curr_xml_str).toprettyxml(indent="  ")
                    except Exception:
                        display_text = curr_xml_str
                st.code(display_text[:8000], language="xml")

    # =============================================================
    # TAB 2: INTERACTIVE XML EDITOR
    # =============================================================
    with tab_edit:
        st.markdown("##### ✏️ Edit XML Tags, Values & Attributes")
        st.caption("Perform targeted modifications on XML elements while strictly preserving structure, attributes, and namespaces.")

        if not xml_files:
            st.info("Please load an XML file to use the XML editor.")
            if st.button("📥 Load sample_data.xml for editing", key="btn_load_sample_xml_edit"):
                xml_sample_p = SAMPLES_DIR / "sample_data.xml"
                if xml_sample_p.exists():
                    with open(xml_sample_p, "rb") as xf:
                        SessionManager.add_uploaded_file("sample_data.xml", xf.read())
                    st.success("Loaded sample_data.xml!")
                    st.rerun()
        else:
            edit_fid = st.selectbox(
                "XML Document to edit:",
                options=list(xml_files.keys()),
                format_func=lambda x: xml_files[x]["filename"],
                key="xml_edit_doc_sel",
            )
            raw_bytes = xml_files[edit_fid]["raw_bytes"]
            try:
                from modules.tally.tally_reader import TallyReader
                active_xml_str = TallyReader.decode_and_sanitize_xml(raw_bytes)[1]
            except Exception:
                active_xml_str = raw_bytes.decode("utf-8", errors="replace")

            # Extract list of available tags for friendly selection
            discovered_tags = sorted(list(set(n["tag"] for n in UniversalXmlEditor.search_nodes(active_xml_str, ""))))

            edit_action = st.selectbox(
                "Choose XML Operation:",
                ["Edit Tag Text", "Rename Tag", "Add / Modify Attribute", "Add Child Element", "Remove Element"],
                key="xml_edit_action_sel",
            )

            e1, e2 = st.columns(2)

            if edit_action == "Edit Tag Text":
                with e1:
                    tag_opt = st.selectbox("Target Tag Name:", options=discovered_tags, key="xml_edit_tag_sel")
                    occ_mode = st.selectbox("Occurrence:", ["First occurrence only", "All matching occurrences"], key="xml_edit_occ_mode")
                with e2:
                    new_val_text = st.text_input("New Text Value:", key="xml_edit_new_text")

                if st.button("Apply Text Update", key="btn_apply_xml_text"):
                    try:
                        occ_idx = -1 if occ_mode == "All matching occurrences" else 0
                        updated_xml, msg = UniversalXmlEditor.edit_node_text(
                            active_xml_str, tag_opt, new_val_text, occurrence_idx=occ_idx
                        )
                        xml_files[edit_fid]["raw_bytes"] = updated_xml.encode("utf-8")
                        xml_files[edit_fid]["size_bytes"] = len(xml_files[edit_fid]["raw_bytes"])
                        
                        # Sync in-memory parsed metadata
                        try:
                            reader = XmlReader()
                            xml_files[edit_fid]["parsed_data"] = reader.read(xml_files[edit_fid]["raw_bytes"])
                            if st.session_state.active_file_id == edit_fid:
                                st.session_state.active_working_df = xml_files[edit_fid]["parsed_data"].get("active_df")
                        except Exception:
                            pass

                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            elif edit_action == "Rename Tag":
                with e1:
                    old_tag = st.selectbox("Current Tag to Rename:", options=discovered_tags, key="xml_rename_old_sel")
                with e2:
                    new_tag = st.text_input("New Tag Name:", value="NEW_TAG", key="xml_rename_new_tag")

                if st.button("Rename Tag", key="btn_apply_xml_rename"):
                    try:
                        updated_xml, msg = UniversalXmlEditor.rename_tag(active_xml_str, old_tag, new_tag)
                        xml_files[edit_fid]["raw_bytes"] = updated_xml.encode("utf-8")
                        xml_files[edit_fid]["size_bytes"] = len(xml_files[edit_fid]["raw_bytes"])
                        
                        try:
                            reader = XmlReader()
                            xml_files[edit_fid]["parsed_data"] = reader.read(xml_files[edit_fid]["raw_bytes"])
                            if st.session_state.active_file_id == edit_fid:
                                st.session_state.active_working_df = xml_files[edit_fid]["parsed_data"].get("active_df")
                        except Exception:
                            pass

                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            elif edit_action == "Add / Modify Attribute":
                with e1:
                    attr_tag = st.selectbox("Target Tag Name:", options=discovered_tags, key="xml_attr_tag_sel")
                    attr_k = st.text_input("Attribute Name (e.g. status):", value="status", key="xml_attr_key")
                with e2:
                    attr_v = st.text_input("Attribute Value (e.g. verified):", value="verified", key="xml_attr_val")

                if st.button("Apply Attribute", key="btn_apply_xml_attr"):
                    try:
                        updated_xml, msg = UniversalXmlEditor.set_attribute(active_xml_str, attr_tag, attr_k, attr_v)
                        xml_files[edit_fid]["raw_bytes"] = updated_xml.encode("utf-8")
                        xml_files[edit_fid]["size_bytes"] = len(xml_files[edit_fid]["raw_bytes"])
                        
                        try:
                            reader = XmlReader()
                            xml_files[edit_fid]["parsed_data"] = reader.read(xml_files[edit_fid]["raw_bytes"])
                            if st.session_state.active_file_id == edit_fid:
                                st.session_state.active_working_df = xml_files[edit_fid]["parsed_data"].get("active_df")
                        except Exception:
                            pass

                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            elif edit_action == "Add Child Element":
                with e1:
                    p_tag = st.selectbox("Parent Tag Name:", options=discovered_tags, key="xml_parent_tag_sel")
                    new_child_tag = st.text_input("New Child Tag Name:", value="STATUS", key="xml_new_child_tag")
                with e2:
                    new_child_text = st.text_input("New Child Text Content:", value="ACTIVE", key="xml_new_child_text")

                if st.button("Add Child Element", key="btn_apply_xml_add_child"):
                    try:
                        updated_xml, msg = UniversalXmlEditor.add_child_element(active_xml_str, p_tag, new_child_tag, new_child_text)
                        xml_files[edit_fid]["raw_bytes"] = updated_xml.encode("utf-8")
                        xml_files[edit_fid]["size_bytes"] = len(xml_files[edit_fid]["raw_bytes"])
                        
                        try:
                            reader = XmlReader()
                            xml_files[edit_fid]["parsed_data"] = reader.read(xml_files[edit_fid]["raw_bytes"])
                            if st.session_state.active_file_id == edit_fid:
                                st.session_state.active_working_df = xml_files[edit_fid]["parsed_data"].get("active_df")
                        except Exception:
                            pass

                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            elif edit_action == "Remove Element":
                root_tag_name = discovered_tags[0] if discovered_tags else ""
                deletable_tags = [t for t in discovered_tags if t != root_tag_name]
                with e1:
                    del_tag = st.selectbox("Tag Name to Remove:", options=deletable_tags or discovered_tags, key="xml_del_tag_sel")
                with e2:
                    confirm_del_xml = st.checkbox(f"Confirm removal of <{del_tag}>", key="chk_confirm_del_xml")

                if st.button("Delete Element", type="primary", disabled=not confirm_del_xml, key="btn_apply_xml_del"):
                    try:
                        updated_xml, msg = UniversalXmlEditor.remove_element(active_xml_str, del_tag)
                        xml_files[edit_fid]["raw_bytes"] = updated_xml.encode("utf-8")
                        xml_files[edit_fid]["size_bytes"] = len(xml_files[edit_fid]["raw_bytes"])
                        
                        try:
                            reader = XmlReader()
                            xml_files[edit_fid]["parsed_data"] = reader.read(xml_files[edit_fid]["raw_bytes"])
                            if st.session_state.active_file_id == edit_fid:
                                st.session_state.active_working_df = xml_files[edit_fid]["parsed_data"].get("active_df")
                        except Exception:
                            pass

                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            st.write("")
            down_c1, down_c2 = st.columns(2)
            with down_c1:
                st.download_button(
                    label="💾 Download Edited XML File",
                    data=xml_files[edit_fid]["raw_bytes"],
                    file_name=f"edited_{xml_files[edit_fid]['filename']}",
                    mime="application/xml",
                    key="btn_download_edited_xml",
                )
            with down_c2:
                if st.button("⭐ Set as Active Dataset in Studio", key="btn_set_edited_active"):
                    SessionManager.set_active_file(edit_fid)
                    st.success("Set as active dataset!")
                    st.rerun()

    # =============================================================
    # TAB 3: EXCEL TO XML SCHEMA MAPPER
    # =============================================================
    with tab_map:
        st.markdown("##### 🗺️ Map Tabular Columns to XML Hierarchy")
        st.caption("Transform any Excel/CSV spreadsheet into structured XML with custom root, record, and nested tag mappings.")

        active_df = SessionManager.get_active_df()
        if active_df is None or active_df.empty:
            st.info("No active tabular dataset loaded. Please load a tabular dataset or load a sample:")
            if st.button("📥 Load Sample Sales Excel (sample_sales.xlsx)", key="btn_load_sales_for_mapping"):
                sales_p = SAMPLES_DIR / "sample_sales.xlsx"
                if sales_p.exists():
                    with open(sales_p, "rb") as sf:
                        SessionManager.add_uploaded_file("sample_sales.xlsx", sf.read())
                    st.success("Loaded sample_sales.xlsx as active dataset!")
                    st.rerun()
        else:
            m_c1, m_c2 = st.columns(2)
            with m_c1:
                schema_root_tag = st.text_input("Root Element Tag:", value="TRANSACTIONS", key="map_xml_root_tag")
            with m_c2:
                schema_rec_tag = st.text_input("Record Element Tag:", value="VOUCHER", key="map_xml_rec_tag")

            st.markdown("###### Configure Column Mappings:")
            st.caption(
                "💡 **Tips:** Prefix target tag with `@` for XML attributes (e.g. `@id`). Use `/` for nested elements (e.g. `CUSTOMER/NAME`)."
            )

            col_mappings = {}
            map_cols = st.columns(3)
            for i, col in enumerate(active_df.columns):
                with map_cols[i % 3]:
                    target_tag = st.text_input(f"'{col}' ->", value=col.upper(), key=f"xml_map_col_{col}")
                    if target_tag.strip():
                        col_mappings[col] = target_tag.strip()

            map_act_c1, map_act_c2 = st.columns(2)
            with map_act_c1:
                if st.button("👁️ Preview First 3 Records XML", key="btn_prev_mapped_xml"):
                    try:
                        preview_xml = UniversalXmlEditor.map_tabular_to_xml(
                            active_df.head(3), root_tag=schema_root_tag, record_tag=schema_rec_tag, mapping=col_mappings
                        )
                        st.code(preview_xml, language="xml")
                    except Exception as pe:
                        st.error(f"Preview error: {str(pe)}")

            with map_act_c2:
                if st.button("🚀 Generate Full Structured XML", type="primary", key="btn_gen_mapped_xml"):
                    try:
                        generated_xml = UniversalXmlEditor.map_tabular_to_xml(
                            active_df, root_tag=schema_root_tag, record_tag=schema_rec_tag, mapping=col_mappings
                        )
                        gen_bytes = generated_xml.encode("utf-8")
                        out_filename = f"{active_file['filename'].rsplit('.', 1)[0]}_mapped.xml"

                        # Register generated XML in session
                        SessionManager.add_uploaded_file(out_filename, gen_bytes)
                        st.success(f"Generated XML document '{out_filename}' and added to Studio memory!")
                        st.code(generated_xml[:3000], language="xml")

                        st.download_button(
                            label="💾 Download Generated XML",
                            data=gen_bytes,
                            file_name=out_filename,
                            mime="application/xml",
                            key="btn_dl_mapped_xml",
                        )
                    except Exception as e:
                        st.error(f"Mapping error: {str(e)}")

    # =============================================================
    # TAB 4: UNIVERSAL CROSS-CONVERTER
    # =============================================================
    with tab_convert:
        st.markdown("##### 🔄 Universal Cross-Format Converter")
        st.caption("Convert datasets cleanly between Excel, CSV, XML, and JSON with hierarchy and structure preservation.")

        conv_pair = st.selectbox(
            "Select Conversion Flow:",
            [
                "Excel to CSV",
                "CSV to Excel",
                "XML to Excel",
                "Excel to XML",
                "JSON to Excel",
                "Excel to JSON",
                "XML to JSON",
                "JSON to XML",
            ],
            key="conv_pair_sel",
        )

        conv_c1, conv_c2 = st.columns([2, 1])

        with conv_c1:
            uploaded_conv_file = st.file_uploader(
                f"Upload source file for {conv_pair}:",
                type=["xlsx", "xls", "csv", "xml", "json", "txt"],
                key="conv_file_uploader",
            )

        with conv_c2:
            st.caption("Or convert current active dataset directly:")
            use_active = st.checkbox("Convert currently active dataset in memory", value=True, key="chk_use_active_conv")

        # Context-specific options
        custom_rec_tag = None
        json_xml_root = "DATASET"
        json_xml_item = "RECORD"

        if conv_pair == "XML to Excel":
            custom_rec_tag = st.text_input("Target Record Tag (optional, auto-detected if left empty):", placeholder="e.g. RECORD, VOUCHER, INVOICE", key="conv_rec_tag_input")
        elif conv_pair == "JSON to XML":
            j_col1, j_col2 = st.columns(2)
            with j_col1:
                json_xml_root = st.text_input("Root Tag:", value="DATASET", key="conv_json_xml_root")
            with j_col2:
                json_xml_item = st.text_input("Item / Record Tag:", value="RECORD", key="conv_json_xml_item")

        st.write("")

        if st.button(f"Execute {conv_pair} Conversion", key="btn_exec_conv"):
            try:
                # Get raw source bytes
                if uploaded_conv_file:
                    raw_src = uploaded_conv_file.read()
                    src_name = uploaded_conv_file.name
                elif use_active and active_file:
                    raw_src = active_file["raw_bytes"]
                    src_name = active_file["filename"]
                    
                    # Validate format compatibility
                    expected_prefix = conv_pair.split(" to ")[0].lower()
                    active_fmt = active_file["format"].lower()
                    if expected_prefix == "excel" and active_fmt != "excel":
                        st.error(f"Active file '{src_name}' is not an Excel file ({active_fmt.upper()}). Please upload an Excel file.")
                        return
                    elif expected_prefix == "csv" and active_fmt not in ["csv", "txt"]:
                        st.error(f"Active file '{src_name}' is not CSV ({active_fmt.upper()}). Please upload a CSV file.")
                        return
                    elif expected_prefix == "xml" and active_fmt != "xml":
                        st.error(f"Active file '{src_name}' is not XML ({active_fmt.upper()}). Please upload an XML file.")
                        return
                    elif expected_prefix == "json" and active_fmt != "json":
                        st.error(f"Active file '{src_name}' is not JSON ({active_fmt.upper()}). Please upload a JSON file.")
                        return
                else:
                    st.error("Please upload a file or select active dataset.")
                    return

                base_out = src_name.rsplit(".", 1)[0]
                out_bytes = None
                out_name = ""
                out_mime = ""

                if conv_pair == "Excel to CSV":
                    res_str = UniversalFormatConverter.excel_to_csv(raw_src)
                    out_bytes = res_str.encode("utf-8")
                    out_name = f"{base_out}.csv"
                    out_mime = "text/csv"

                elif conv_pair == "CSV to Excel":
                    out_bytes = UniversalFormatConverter.csv_to_excel(raw_src.decode("utf-8", errors="replace"))
                    out_name = f"{base_out}.xlsx"
                    out_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

                elif conv_pair == "XML to Excel":
                    out_bytes = UniversalFormatConverter.xml_to_excel(
                        raw_src.decode("utf-8", errors="replace"),
                        record_tag=custom_rec_tag or None,
                    )
                    out_name = f"{base_out}.xlsx"
                    out_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

                elif conv_pair == "Excel to XML":
                    res_str = UniversalFormatConverter.excel_to_xml(raw_src)
                    out_bytes = res_str.encode("utf-8")
                    out_name = f"{base_out}.xml"
                    out_mime = "application/xml"

                elif conv_pair == "JSON to Excel":
                    out_bytes = UniversalFormatConverter.json_to_excel(raw_src.decode("utf-8", errors="replace"))
                    out_name = f"{base_out}.xlsx"
                    out_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

                elif conv_pair == "Excel to JSON":
                    res_str = UniversalFormatConverter.excel_to_json(raw_src)
                    out_bytes = res_str.encode("utf-8")
                    out_name = f"{base_out}.json"
                    out_mime = "application/json"

                elif conv_pair == "XML to JSON":
                    res_str = UniversalFormatConverter.xml_to_json(raw_src.decode("utf-8", errors="replace"))
                    out_bytes = res_str.encode("utf-8")
                    out_name = f"{base_out}.json"
                    out_mime = "application/json"

                elif conv_pair == "JSON to XML":
                    res_str = UniversalFormatConverter.json_to_xml(
                        raw_src.decode("utf-8", errors="replace"),
                        root_tag=json_xml_root or "DATASET",
                        item_tag=json_xml_item or "RECORD",
                    )
                    out_bytes = res_str.encode("utf-8")
                    out_name = f"{base_out}.xml"
                    out_mime = "application/xml"

                if out_bytes:
                    st.success(f"Converted '{src_name}' using {conv_pair} successfully!")
                    st.session_state["last_converted_bytes"] = out_bytes
                    st.session_state["last_converted_name"] = out_name
                    st.session_state["last_converted_mime"] = out_mime

            except Exception as e:
                st.error(f"Conversion error: {str(e)}")

        # Render download / session load buttons if conversion result is available
        if "last_converted_bytes" in st.session_state:
            conv_d1, conv_d2 = st.columns(2)
            with conv_d1:
                st.download_button(
                    label=f"💾 Download Converted File ({st.session_state['last_converted_name']})",
                    data=st.session_state["last_converted_bytes"],
                    file_name=st.session_state["last_converted_name"],
                    mime=st.session_state["last_converted_mime"],
                    key="dl_conv_btn_action",
                )
            with conv_d2:
                if st.button("📥 Load Converted File into Studio Session", key="btn_load_conv_to_session"):
                    SessionManager.add_uploaded_file(
                        st.session_state["last_converted_name"],
                        st.session_state["last_converted_bytes"],
                    )
                    st.success(f"Loaded '{st.session_state['last_converted_name']}' into Studio memory as active file!")
                    st.rerun()


if __name__ == "__main__":
    show()
