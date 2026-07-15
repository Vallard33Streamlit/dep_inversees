import streamlit as st
import pandas as pd
import numpy as np
from copy import deepcopy

st.set_page_config(layout="wide")
# --- 1. Initialisation des données (cachée) ---
st.header("Dépendances inversées")
@st.cache_data
def load_baci():
    l_bacis = []
    for i in range (5):
        l_bacis.append(pd.read_csv(f"baci{i+1}.csv", dtype={"k": str}))
    baci = pd.concat(l_bacis)

    countries_config = pd.read_csv("country_codes.csv", sep=";")[["country_code", "nom_pays"]]
    countries_config= countries_config[countries_config["country_code"].isin(set(baci["i"].unique()) | set(baci["j"].unique()))]

    countries_config["country"] = True
    countries_config["zone"] = np.nan
    l_ue = [276, 40, 6, 100, 196, 191, 208, 724, 233, 246, 251, 300, 348, 372, 380, 428, 440, 442, 470, 528, 616, 620, 642, 703, 705, 752, 203]
    countries_config.loc[1000] = 1000, "UE", False, np.nan
    countries_config.loc[countries_config['country_code'].isin(set(l_ue)), "zone"] = 1000

    return baci, countries_config

@st.cache_data
def load_labels():
    return pd.read_csv("labels_hs6.csv", dtype={"Code HS6": str})

def calc_baci2(countries_config):
    baci2 = baci.merge(countries_config.loc[countries_config["zone"].notna(), ["country_code", "zone"]], left_on="i", right_on="country_code", how="left")
    baci2.loc[baci2["zone"].notna(), "i"] = baci2.loc[baci2["zone"].notna(), "zone"] 
    baci2.drop(columns=["country_code", "zone"], inplace=True)
    baci2 = baci2.merge(countries_config.loc[countries_config["zone"].notna(), ["country_code", "zone"]], left_on="j", right_on="country_code", how="left")
    baci2.loc[baci2["zone"].notna(), "j"] = baci2.loc[baci2["zone"].notna(), "zone"]
    baci2.drop(columns=["country_code", "zone"], inplace=True)
    baci2 = baci2[baci2["i"] != baci2['j']]
    return baci2.groupby(["i","j","k"])[["v", "q"]].sum().reset_index()

def calc_c(baci2, type, country=0):
    if type == "imp":
        x, y = "j", "i"
        type_o = "exp"
    else:
        x, y = "i", "j"
        type_o = "imp"
    if country == 0:
        type2="m"
        baci3 = baci2.groupby(["k", y])[["v", "q"]].sum().reset_index()
    else:
        type2 = "c"
        baci3 = baci2[baci2[x] == country].copy()

    hhi_c =baci3.groupby("k").agg(
            v=("v", "sum"),
            q=("q", "sum"),
            hhi=("v", lambda x: (x ** 2).sum())
    ).rename(columns={col : f"{col}_{type}_{type2}" for col in ["v", "q", "hhi"]}).reset_index()

    temp = baci3.groupby('k').apply(lambda x: x.nlargest(3, 'v')[['v', y]])
    temp["n"] = temp.groupby(level="k").cumcount() + 1
    temp = temp.reset_index(level="k")
    top3 = temp.pivot(index="k", columns="n")
    top3.columns = [f"{col}{n}" for col, n in top3.columns]
    top3.reset_index(inplace=True)
    top3.rename(columns={col : f"cc_{type_o}_max_{col[-1]}_{type2}_{type}" for col in top3.columns if col[0]==y}, inplace=True)
    top3.rename(columns={col : f"p_{type_o}_max_{col[-1]}_{type2}_{type}" for col in top3.columns if col[0]=="v"}, inplace=True)

    df_tot = hhi_c.merge(top3, how="outer")
    df_tot[f"hhi_{type}_{type2}"] /= (df_tot[f"v_{type}_{type2}"]**2)
    for col in df_tot.columns:
        if col[0] == "p":
            df_tot[col] = df_tot[col].fillna(0) / df_tot[f"v_{type}_{type2}"]

    df_tot = df_tot.merge(baci3.loc[baci3[y] == st.session_state.fr_ue, ["k", "v"]].groupby("k").sum().reset_index().rename(columns={"v":f"p_{type_o}_fr_ue_{type}_{type2}"}), how="outer")
    df_tot[f"p_{type_o}_fr_ue_{type}_{type2}"] = df_tot[f"p_{type_o}_fr_ue_{type}_{type2}"].fillna(0) / df_tot[f"v_{type}_{type2}"]
    
    if country != 0:
        baci4 = baci2[baci2[y] == st.session_state.fr_ue]
        temp = baci4[baci4[x] == country].merge(baci4.groupby("k")["v"].sum().rename("v_sum").reset_index(), how="outer")
        temp[f"p_{type}_{type2}_{type_o}_fr_ue"] = temp["v"].fillna(0) / temp["v_sum"]
        df_tot = df_tot.merge(temp[["k", f"p_{type}_{type2}_{type_o}_fr_ue"]], how="outer")
    return df_tot

def maj(c):
    return c[0].upper() + c[1:]

if "compt_z_infl" not in st.session_state:
    st.session_state.compt_z_infl = 2

baci, countries_config = load_baci()
labels = load_labels()

# --- 2. Initialisation de la configuration dans session_state ---
if "countries_config" not in st.session_state:
    st.session_state.countries_config = deepcopy(countries_config)
c_config = st.session_state.countries_config
if "modified_z_infl" not in st.session_state:
    st.session_state.modified_z_infl = True  # Flag pour savoir si des modifications sont en attente
if "modified_sel_country" not in st.session_state:
    st.session_state.modified_sel_country = True


# --- 3. Éditeur de zones (onglet dédié) ---
with st.expander("**Éditer les zones d'influence**", expanded=True):
    st.markdown("Modifier les zones et leurs pays, puis valider avec le bouton en bas.")
    # --- Ajout d'une nouvelle zone ---
    new_zone_name = st.text_input("Nom de la nouvelle zone", value ="Zone d'influence", key=f"new_zone_input")
    if st.button("➕ Ajouter une zone", key="add_zone_btn") and new_zone_name:
        if new_zone_name == "Zone d'influence":
            new_zone_name += f" {st.session_state.compt_z_infl}"
        if new_zone_name not in c_config["nom_pays"].values:
            c_config.loc[1000+st.session_state.compt_z_infl] = 1000+st.session_state.compt_z_infl, new_zone_name, False, np.nan
            st.session_state.modified_z_infl = True
            st.toast(f"Zone '{new_zone_name}' ajoutée !")
            st.session_state.compt_z_infl += 1
        else:
            st.error(new_zone_name + " existe déjà.")
    # --- Édition des zones existantes ---
    for zone in list(c_config.loc[~c_config["country"], "country_code"].unique()):
        col1, col2, col3 = st.columns([1, 8, 1])
        with col1:
            # Renommage de la zone
            new_name = st.text_input(
                "Nom de la zone",
                value=c_config.loc[c_config["country_code"] == zone, "nom_pays"].iloc[0],
                key=f"zone_name_{zone}",
                label_visibility="collapsed"
            )
            if new_name != c_config.loc[c_config["country_code"] == zone, "nom_pays"].iloc[0]:
                if new_name not in c_config["nom_pays"].values:
                    c_config.loc[c_config["country_code"] == zone, "nom_pays"] = new_name
                    st.session_state.modified_z_infl = True
                else:
                    st.error(new_name + " existe déjà.")
        with col2:
            # Sélection des pays pour cette zone
            selected_countries = st.multiselect(
                "Pays associés",
                options=sorted(list(c_config.loc[(c_config["country"]&c_config["zone"].isna()) | (c_config["zone"] == zone), "nom_pays"])),
                default=list(c_config.loc[c_config["zone"] == zone, "nom_pays"]),
                key=f"countries_{zone}",
                label_visibility="collapsed"
            )
            temp = set(c_config.loc[c_config["zone"] == zone, "nom_pays"])
            if set(selected_countries) != temp:
                c_config.loc[c_config['nom_pays'].isin(set(selected_countries) - temp),"zone"] = zone
                c_config.loc[c_config['nom_pays'].isin(temp - set(selected_countries)), "zone"] = np.nan
                st.session_state.modified_z_infl = True

        with col3:
            # Suppression de la zone
            if st.button("🗑️", key=f"del_zone_{zone}"):
                c_config.drop(zone, inplace=True)
                st.session_state.modified_z_infl = True
                st.rerun()

    # --- Bouton de validation globale ---
    if st.session_state.modified_z_infl:
        if st.button("💾 **Enregistrer la configuration**", type="primary"):
            st.session_state.modified_z_infl = False
            # st.toast("Configuration enregistrée ! Les filtres seront appliqués après validation.")
            st.session_state.modified_sel_country = True
            if c_config.loc[c_config["country_code"] == 251, "zone"].isna().any():
                st.session_state.fr_ue = 251
            else :
                st.session_state.fr_ue = c_config.loc[c_config["country_code"] == 251, "zone"].iloc[0]
            st.session_state.baci2 = calc_baci2(c_config)
            st.session_state.df_m = calc_c(st.session_state.baci2, "imp", 0).merge(calc_c(st.session_state.baci2, "exp", 0), how="outer")
            

if not st.session_state.modified_z_infl:
    with st.expander("**Sélectionner un pays à étudier**", expanded=True):

        selected_country = st.selectbox(
            "Pays à étudier",
            options=sorted(list(c_config.loc[c_config["zone"].isna(), "nom_pays"])),
            key="selected_country",
            on_change=lambda: st.session_state.update(modified_sel_country=True)
        )
        if st.session_state.modified_sel_country:
            selected_country_code = c_config.loc[c_config["nom_pays"] == st.session_state.selected_country, "country_code"].iloc[0]
            if st.button("🔍 **Appliquer les filtres**"):
                st.session_state.modified_sel_country = False
                st.session_state.df_final = calc_c(st.session_state.baci2, "imp", selected_country_code).merge(calc_c(st.session_state.baci2, "exp", selected_country_code), how="outer").merge(st.session_state.df_m, how="outer")
                for col in st.session_state.df_final.columns:
                    if (col[0] == "v") | (col[0] == "q") | (col[0] == "p"):
                        st.session_state.df_final[col] = st.session_state.df_final[col].fillna(0)
                if c_config.loc[c_config["country_code"] == 251, "zone"].isna().all():
                    st.session_state.fr_ue_lab = "la France"
                else:
                    st.session_state.fr_ue_lab = "l'UE"
                st.session_state.df_final.rename(columns={"k":"Code HS6"}, inplace=True)
                st.session_state.df_final = st.session_state.df_final.merge(labels, how="left")
                st.session_state.df_final["Code HS4"] = st.session_state.df_final["Code HS6"].apply(lambda x : x[:4])
                st.session_state.df_final = st.session_state.df_final.merge(labels.rename(columns={"Code HS6":"Code HS4", "Label HS6":"Label HS4"}), how="left")
                st.session_state.df_final.columns = ["Code HS6", "Importations du pays", "Quantités importées du pays", "HHi des importations du pays",
                    "Part du premier exportateur dans les importations du pays", "Part du deuxième exportateur dans les importations du pays", "Part du troisième exportateur dans les importations du pays", 
                    "Premier exportateur dans les importations du pays", "Deuxième exportateur dans les importations du pays", "Troisième exportateur dans les importations du pays", 
                    f"Part des exportations de {st.session_state.fr_ue_lab} dans les importations du pays", f"Part des importations du pays dans les exportations de {st.session_state.fr_ue_lab}", 
                    "Exportations du pays", "Quantités exportées du pays", "HHi des exportations du pays",
                    "Part du premier importateur dans les exportations du pays", "Part du deuxième importateur dans les exportations du pays", "Part du troisième importateur dans les exportations du pays", 
                    "Premier importateur dans les exportations du pays", "Deuxième importateur dans les exportations du pays", "Troisième importateur dans les exportations du pays",
                    f"Part des importations de {st.session_state.fr_ue_lab} dans les exportations du pays", f"Part des exportations du pays dans les importations de {st.session_state.fr_ue_lab}", 
                    "Valeur des flux échangés dans le monde", "Quantités échangées dans le monde", "HHi des exportations mondiales",
                    "Part du premier exportateur mondial", "Part du deuxième exportateur mondial", "Part du troisième exportateur mondial",
                    "Premier exportateur mondial", "Deuxième exportateur mondial", "Troisième exportateur mondial",
                    f"Part des exportations de {st.session_state.fr_ue_lab} dans le monde",
                    "a supprimer", "a supprimer 2", "HHi des importations mondiales",
                    "Part du premier importateur mondial", "Part du deuxième importateur mondial", "Part du troisième importateur mondial",
                    "Premier importateur mondial", "Deuxième importateur mondial", "Troisième importateur mondial",
                    f"Part des importations de {st.session_state.fr_ue_lab} dans le monde",
                    "Label HS6", "Code HS4", "Label HS4"]
                l_cols = ["Code HS6", "Label HS6",
                    f"Part des exportations de {st.session_state.fr_ue_lab} dans les importations du pays", f"Part des importations du pays dans les exportations de {st.session_state.fr_ue_lab}", "HHi des importations du pays",
                    f"Part des importations de {st.session_state.fr_ue_lab} dans les exportations du pays", f"Part des exportations du pays dans les importations de {st.session_state.fr_ue_lab}", "HHi des exportations du pays",
                    "HHi des exportations mondiales", "HHi des importations mondiales",
                    "Importations du pays", "Quantités importées du pays",
                    "Exportations du pays", "Quantités exportées du pays",
                    "Valeur des flux échangés dans le monde", "Quantités échangées dans le monde",
                    f"Part des exportations de {st.session_state.fr_ue_lab} dans le monde", f"Part des importations de {st.session_state.fr_ue_lab} dans le monde",
                    "Code HS4", "Label HS4",
                    "Part du premier exportateur dans les importations du pays", "Part du deuxième exportateur dans les importations du pays", "Part du troisième exportateur dans les importations du pays",          
                    "Part du premier importateur dans les exportations du pays", "Part du deuxième importateur dans les exportations du pays", "Part du troisième importateur dans les exportations du pays", 
                    "Part du premier exportateur mondial", "Part du deuxième exportateur mondial", "Part du troisième exportateur mondial",
                    "Part du premier importateur mondial", "Part du deuxième importateur mondial", "Part du troisième importateur mondial",
                    "Premier exportateur dans les importations du pays", "Deuxième exportateur dans les importations du pays", "Troisième exportateur dans les importations du pays", 
                    "Premier importateur dans les exportations du pays", "Deuxième importateur dans les exportations du pays", "Troisième importateur dans les exportations du pays", 
                    "Premier exportateur mondial", "Deuxième exportateur mondial", "Troisième exportateur mondial",
                    "Premier importateur mondial", "Deuxième importateur mondial", "Troisième importateur mondial"]
                st.session_state.df_final = st.session_state.df_final[l_cols]
    # --- 5. Application des filtres (uniquement après validation) ---
    if not st.session_state.modified_sel_country:
        df_final_mod = st.session_state.df_final.copy()
        st.subheader("Filtres")

        type_filter = st.radio(
            "S'intéresser aux produits :",
            options=["Tous", "Nettement importés", "Nettement exportés"],
            index=0
        )
        if type_filter == "Nettement importés":
            type, type2 = "imp", "exp"
        elif type_filter == "Nettement exportés":
            type, type2 = "exp", "imp"
        if type_filter != "Tous":
            l_cols_2 = ["Code HS6", "Label HS6",
                f"Part des {type2}ortations de {st.session_state.fr_ue_lab} dans les {type}ortations du pays", f"Part des {type}ortations du pays dans les {type2}ortations de {st.session_state.fr_ue_lab}", f"HHi des {type}ortations du pays",
                f"HHi des {type2}ortations mondiales", f"{maj(type)}ortations du pays", f"Quantités {type}ortées du pays", f"{maj(type2)}ortations du pays", f"Quantités {type2}ortées du pays",
                "Valeur des flux échangés dans le monde", "Quantités échangées dans le monde",
                f"Part des {type2}ortations de {st.session_state.fr_ue_lab} dans le monde",
                "Code HS4", "Label HS4",
                f"Part du premier {type2}ortateur dans les {type}ortations du pays", f"Part du deuxième {type2}ortateur dans les {type}ortations du pays", f"Part du troisième {type2}ortateur dans les {type}ortations du pays",          
                f"Part du premier {type2}ortateur mondial", f"Part du deuxième {type2}ortateur mondial", f"Part du troisième {type2}ortateur mondial",
                f"Premier {type2}ortateur dans les {type}ortations du pays", f"Deuxième {type2}ortateur dans les {type}ortations du pays", f"Troisième {type2}ortateur dans les {type}ortations du pays", 
                f"Premier {type2}ortateur mondial", f"Deuxième {type2}ortateur mondial", f"Troisième {type2}ortateur mondial"]

            df_final_mod = df_final_mod[(df_final_mod[f"{maj(type)}ortations du pays"] >= df_final_mod[f"{maj(type2)}ortations du pays"])&(df_final_mod[f"{maj(type)}ortations du pays"] > 0)]
            df_final_mod = df_final_mod[l_cols_2]
        
            filter_by_hhi_c = st.checkbox(f"Filtrer les produits selon l'indice HHi des {type}ortations du pays", key="filter_by_hhi_c")
            if filter_by_hhi_c:
                hhi_c = st.slider(f"HHi des {type}ortations supérieur à :", min_value=0.0, max_value=1.0, value=0.25, step=0.01, format="%.2f")
                df_final_mod = df_final_mod[df_final_mod[f"HHi des {type}ortations du pays"] >= hhi_c]

            filter_by_hhi_m = st.checkbox(f"Filtrer les produits selon l'indice HHi mondial des {type2}ortations", key="filter_by_hhi_m")
            if filter_by_hhi_m:
                hhi_M = st.slider(f"HHi mondial des {type2}ortations supérieur à :", min_value=0.0, max_value=1.0, value=0.25, step=0.01, format="%.2f")
                df_final_mod = df_final_mod[df_final_mod[f"HHi des {type2}ortations mondiales"] >= hhi_M]

            filter_by_p_fr_ue_in_c = st.checkbox(f"Filtrer les produits selon la part des {type2}ortations de {st.session_state.fr_ue_lab} dans les {type}ortations du pays", key="filter_by_p_fr_ue_in_c")
            if filter_by_p_fr_ue_in_c:
                p_fr_ue_in_c = st.slider(f"Part des {type2}ortations de {st.session_state.fr_ue_lab} dans les {type}ortations du pays supérieure à :", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.2f")
                df_final_mod = df_final_mod[df_final_mod[f"Part des {type2}ortations de {st.session_state.fr_ue_lab} dans les {type}ortations du pays"] >= p_fr_ue_in_c]

            filter_by_p_c_in_fr_ue = st.checkbox(f"Filtrer les produits selon la part des {type}ortations du pays dans les {type2}ortations de {st.session_state.fr_ue_lab}", key="filter_by_p_c_in_fr_ue")
            if filter_by_p_c_in_fr_ue:
                p_c_in_fr_ue = st.slider(f"Part des {type}ortations du pays dans les {type2}ortations de {st.session_state.fr_ue_lab} inférieure à :", min_value=0.0, max_value=1.0, value=0.5, step=0.01, format="%.2f")
                df_final_mod = df_final_mod[df_final_mod[f"Part des {type}ortations du pays dans les {type2}ortations de {st.session_state.fr_ue_lab}"] <= p_c_in_fr_ue]

            log_values = np.linspace(-3, 6, 901)
            filter_by_v = st.checkbox(f"Filtrer les produits selon le montant des {type}ortations du pays ", key="filter_by_v")
            if filter_by_v:
                log_value_v = st.select_slider(f"Montant des {type}ortations (en 1000$) supérieur à :", options=log_values, value=0, format_func=lambda x: f"{10**x:.3f}")
                df_final_mod = df_final_mod[df_final_mod[f"{maj(type)}ortations du pays"] >= 10**log_value_v]


        st.subheader("Résultats")
        st.write(f"Il y a {len(df_final_mod)} produits (HS6)")
        st.dataframe(df_final_mod)

        # Export CSV
        st.download_button(
            "📥 Télécharger les données filtrées",
            df_final_mod.to_csv(index=False).encode("utf-8"),
            "data_filtrees.csv",
            "text/csv"
        )

