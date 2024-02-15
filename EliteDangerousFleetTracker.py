import sqlite3
import webbrowser
from Account import TokenRequestType
from Account import Account
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
import logging
from enum import Enum

GUI_LABEL_REFRESH_INTERVAL = 1000


class Owner(Enum):
    NONE = 0
    CAPI = 1
    ACCOUNT = 2
    COMMANDER = 3
    FLEETCARRIER = 4
    DELETE = 5


""" Dynamic Label Entry Indices """
LABEL = 0
ACCOUNT = 1
COLUMN = 2

""" The Ladder """
LADDER = {
    "Gali": "N16",
    "Wregoe ZE-B c28-2": "N15",
    "Wregoe OP-D b58-0": "N14",
    "Plaa Trua QL-B c27-0": "N13",
    "Plaa Trua WQ-C d13-0": "N12",
    "HD 107865": "N11",
    "HD 105548": "N10",
    "HD 104785": "N9",
    "HD 102000": "N8",
    "HD 102779": "N7",
    "HD 104392": "N6",
    "HIP 56843": "N5",
    "HIP 57478": "N4",
    "HIP 57784": "N3",
    "HD 104495": "N2",
    "HD 105341": "N1",
    "HIP 58832": "N0",
}


def dynamic_item_spec(owner, display_name, keys, post_processors) -> dict:
    """
    Creates a dynamic column specification, which contains the column group (and thus the appropriate data source), the
    name of the column, the keys required to index down to the appropriate data item from the data source, and any
    post-processing functions to be applied to the data after indexing.
    :param owner: Defines the display column grouping to which this item belongs, and also the stored data structure
    that contains the data item. Options are given in the Owner enum above.
    :param display_name: The name of the column, as displayed in the column headers
    :param keys: A tuple of string keys, given in the appropriate order, to index from the high-level data structure
    down to the individual data item to be displayed. For example for the commander name, which is part of the cmdr_data
    structure, the keys tuple is ("commander", "name"), corresponding to cmdr_data["commander"]["name"]. Can be None,
    which is useful if the data item is being generated entirely by a post-processor function defined below rather than
    a single item indexed from a data .
    :param post_processors: A tuple of function handles, to be applied--in the order they appear in the tuple--to the
    data item returned from the indexing operation. Function `self.passthrough` is provided to handle cases where no
    post-processing is required. Simpler than adding logic to handle None here.
    :return: a column specification dict, containing the above parameters.
    """
    return {
        "owner": owner,
        "display_name": display_name,
        "keys": keys,
        "post_processors": post_processors,
    }


class EliteDangerousFleetTracker:
    conn = None
    log_handler = None
    account_table = None
    frm1 = None
    frm2 = None
    frm3 = None
    root = None
    tab_control = None
    dynamic_labels = []
    capi_buttons = []
    input_box = None
    ready_accounts = 0
    columns = None

    def __init__(self, conn, log_handler):
        self.version = "0.2.0"
        self.conn = conn
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.log_handler = log_handler
        self.logger.addHandler(log_handler)
        self.logger.debug("Starting up main EDFT instance")
        self.columns = [
            dynamic_item_spec(Owner.DELETE, "", None, (self.delete_column,)),
            dynamic_item_spec(Owner.CAPI, "cAPI", None, (self.capi_column,)),
            dynamic_item_spec(
                Owner.ACCOUNT, "Nickname", ("name",), (self.passthrough,)
            ),
            dynamic_item_spec(
                Owner.COMMANDER, "Name", ("commander", "name"), (self.passthrough,)
            ),
            dynamic_item_spec(
                Owner.COMMANDER,
                "Balance",
                ("commander", "credits"),
                (self.currency_format,),
            ),
            dynamic_item_spec(
                Owner.COMMANDER,
                "Station",
                ("ship", "station", "name"),
                (self.passthrough,),
            ),
            dynamic_item_spec(
                Owner.COMMANDER,
                "System",
                ("ship", "starsystem", "name"),
                (self.passthrough,),
            ),
            dynamic_item_spec(
                Owner.COMMANDER,
                "N#",
                ("ship", "starsystem", "name"),
                (self.ladder_display,),
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER,
                "Callsign",
                ("name", "callsign"),
                (self.passthrough,),
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER,
                "Name",
                ("name", "filteredVanityName"),
                (self.hex_decode,),
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER, "Fuel", ("fuel",), (self.passthrough,)
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER,
                "Tonnage",
                ("capacity",),
                (self.calculate_tonnage, self.currency_format),
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER, "Balance", ("balance",), (self.currency_format,)
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER,
                "System",
                ("currentStarSystem",),
                (self.passthrough,),
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER,
                "N#",
                ("currentStarSystem",),
                (self.ladder_display,),
            ),
            dynamic_item_spec(
                Owner.FLEETCARRIER,
                "Ghost Sells",
                ("orders", "commodities", "sales"),
                (self.ghost_orders,),
            ),
        ]

    def create_gui(self) -> None:
        """
        Creates the main Tk GUI elements
        :return: None
        """
        self.root = Tk()
        self.tab_control = ttk.Notebook(self.root, padding=10)
        self.frm2 = ttk.Frame(self.tab_control, padding=10)
        self.tab_control.add(self.frm2, text="None of Your Business")
        self.create_main_frame(self.tab_control)
        self.tab_control.pack(expand=1, fill="both")
        self.root.title("Elite Dangerous Fleet Tracker v" + self.version)
        self.root.mainloop()

    def create_main_frame(self, parent) -> None:
        """
        Creates the "Main" tab of the GUI that contains the summary data
        :param parent: the main Tk GUI container
        :return: None
        """
        self.frm1 = ttk.Frame(parent, padding=10)
        self.frm1.grid()
        last_row, last_col = self.create_table(self.frm1)
        # ttk.Button(self.frm1, text="test", command=self.test).grid(column=last_col - 2, row=last_row + 2)
        ttk.Button(self.frm1, text="Quit", command=self.root.destroy).grid(
            column=last_col, row=last_row + 2
        )
        self.frm1.pack()
        parent.add(self.frm1, text="Main")
        parent.select(parent.index("end") - 1)
        self.root.after(GUI_LABEL_REFRESH_INTERVAL, self.update_dynamic_labels)

    def update_dynamic_labels(self) -> None:
        """
        This is automatically called every GUI_LABEL_REFRESH_INTERVAL ms to update the table entries. It is essentially
        the main polling loop in the GUI thread and has outgrown its original purpose. Should probably be refactored
        thoon.

        This method currently manages the labels, the database polling while waiting for the code from the API endpoint
        to generate new tokens, and the synchronization of the account table in memory with the one on disk.
        :return: None
        """
        try:
            new_ready_accounts = self.count_ready_accounts()
            if new_ready_accounts > self.ready_accounts:
                self.logger.debug("found new account")
                self.recreate_main_frame()
            self.ready_accounts = new_ready_accounts
            for entry in self.dynamic_labels:
                # Update each Dynamic Label as long as the account is current.
                # Update CAPI, Account, None, and Delete columns always.
                if (
                    entry[COLUMN]["owner"] is Owner.CAPI
                    or entry[COLUMN]["owner"] is Owner.ACCOUNT
                    or entry[COLUMN]["owner"] is Owner.DELETE
                    or entry[COLUMN]["owner"] is Owner.NONE
                    or not entry[ACCOUNT].reauth_required
                ):
                    txt = self.generate_dynamic_label_text(entry)
                    entry[LABEL].configure(text=txt)

                # Additional behavior for cAPI column:
                if entry[COLUMN]["owner"] == Owner.CAPI:
                    account = entry[ACCOUNT]
                    if account.reauth_required and not account.reauth_prompted:
                        account.setup_uri(TokenRequestType.INITIAL)
                        entry[LABEL].bind(
                            "<Button-1>", lambda e: self.generate_capi_uri(e)
                        )
                    if account.reauth_prompted:
                        cur = self.conn.cursor()
                        res = cur.execute(
                            "select code from accounts where name = ? and code is not null",
                            (account.name,),
                        )
                        code = res.fetchone()
                        if code is not None:
                            account.set_code(code[0])
                            self.logger.debug("obtaining tokens")
                            account.obtain_tokens(TokenRequestType.INITIAL)
                            self.logger.debug("capi update for just this account")
                            account.update_from_capi()

                # Additional behavior for delete column
                if entry[COLUMN]["owner"] == Owner.DELETE:
                    entry[LABEL].bind(
                        "<Button-1>", lambda e: self.remove_account_callback(e)
                    )

            # Finally, check to see if any accounts need to be synced to disk. If so, do it now.
            for account in self.account_table:
                if account.needs_sync:
                    account.sync_to_database()
            self.root.after(GUI_LABEL_REFRESH_INTERVAL, self.update_dynamic_labels)
        except:
            """Over-broad exception handling sure, but at least it doesn't swallow?"""
            self.logger.exception("")

    def test(self):
        # test code goes here
        pass

    def init_account_table(self) -> None:
        """
        This reads the account table from storage and loads it into memory. It constructs an Account object for each
        account found on disk and places them in the account table for later retrieval.
        :return: None
        """
        self.account_table = []
        cur = self.conn.cursor()
        try:
            names = cur.execute("select name from accounts").fetchall()
            for name in names:
                self.account_table.append(Account(self.conn, self.log_handler, name[0]))
        except sqlite3.OperationalError:
            self.logger.exception("empty DB?")
        self.ready_accounts = self.count_ready_accounts()

    def generate_dynamic_label_text(self, dynamic_label_tuple) -> str:
        """
        Returns the text that should appear in the label defined by the input tuple. Fetches data from cache, indexes
        and applies post-processors as defined in the column specification.

        Design is the Owner of the column defines which data cache holds the target value, and to which group of columns
        the data belongs. So far this has not caused any problems-- there has been no need to interleave data about the
        commander and data about the fleet carrier.
        :param dynamic_label_tuple: Contains reference to the label object, the account to which the data belongs, and
        the column specification that governs the formatted output data (in that order).
        :return: The label text, after all post-processors have been applied. Guaranteed to be str.
        """
        column = dynamic_label_tuple[COLUMN]
        account = dynamic_label_tuple[ACCOUNT]
        match column["owner"]:
            case Owner.ACCOUNT | Owner.CAPI | Owner.DELETE:
                prior = account
            case Owner.COMMANDER:
                prior = account.cmdr_data
            case Owner.FLEETCARRIER:
                prior = account.fc_data
            case Owner.NONE:
                prior = None
            case _:
                prior = None
                self.logger.error("Invalid Owner Type Passed: " + str(column["owner"]))

        if column["keys"] is not None:
            for key in column["keys"]:
                prior = prior.get(key)
        if column["post_processors"] is not None:
            for postproc in column["post_processors"]:
                prior = postproc(prior)

        txt = prior
        return txt

    def dynamic_gridded_label(
        self, parent, row, col, account, column_spec=None
    ) -> None:
        """
        Creates a dynamic label and appends a reference to it to the dynamic labels list for later update.
        :param parent: the GUI element that contains the Label grid
        :param row: which row in the Label grid the Label lives in
        :param col: which column in the Label grid the Label lives in
        :param account: The account (in the account table) to which the data belongs
        :param column_spec: The column spec that applies to this entry
        :return: nothing
        """
        if column_spec is None:
            column = self.columns[col]
        else:
            column = column_spec
        if account is None or (
            (not account.reauth_required or column["owner"] is Owner.CAPI)
            and account.fc_data is not None
            and account.cmdr_data is not None
        ):
            txt = self.generate_dynamic_label_text((None, account, column))
        else:
            txt = "-"
        label = ttk.Label(parent, text=txt, anchor="w", background="azure")
        label.grid(row=row, column=col, sticky="nsew")

        self.dynamic_labels.append((label, account, column))

    def create_header_row(self, parent, header_row) -> [int, int]:
        """
        Creates the table header rows. Column specs are pulled from `self.columns`
        :param parent: the GUI element that contains the Label grid array
        :param header_row: Which row of the Label grid array to place the top header row on
        :return: the total number of columns, the row number immediately beneath the headers
        """
        col_start = 0
        account_cols = 0
        cmdr_cols = 0
        fc_cols = 0
        for column in self.columns:
            match column["owner"]:
                case Owner.ACCOUNT | Owner.CAPI | Owner.DELETE:
                    account_cols += 1
                case Owner.COMMANDER:
                    cmdr_cols += 1
                case Owner.FLEETCARRIER:
                    fc_cols += 1
                case _:
                    self.logger.error(
                        "Invalid Column Group Owner Passed: " + str(column["owner"])
                    )
        ttk.Label(parent, text="Account Info", justify=CENTER).grid(
            row=header_row, column=col_start, columnspan=account_cols, sticky="nsew"
        )
        ttk.Label(parent, text="Commander Info", justify=CENTER).grid(
            row=header_row,
            column=col_start + account_cols,
            columnspan=cmdr_cols,
            sticky="nsew",
        )
        ttk.Label(parent, text="Fleet Carrier Info", justify=CENTER).grid(
            row=header_row,
            column=col_start + account_cols + cmdr_cols,
            columnspan=fc_cols,
            sticky="nsew",
        )
        header_row += 1
        col = 0
        for entry in self.columns:
            ttk.Label(parent, text=entry["display_name"], anchor="w").grid(
                row=header_row, column=col, sticky="nsew"
            )
            col += 1
        header_row += 1
        return col - 1, header_row

    def dynamic_table_row(self, parent, row, colstart, account) -> None:
        """
        Creates an individual data row.
        :param parent: The GUI element that contains the Label grid array
        :param row: Which row of the Label grid array to place this data row on
        :param colstart: The column where we begin populating data
        :param account: The account who owns the data for this row
        :return: Nothing
        """
        col = colstart
        for column in self.columns:
            self.dynamic_gridded_label(parent, row, col, account)
            col += 1

    def create_table(self, parent) -> [int, int]:
        """
        Creates the label grid array, adds GUI elements to add new accounts, and displays liquid assets
        :param parent: the GUI element that contains the Label grid array
        :return: the row immediately beneath the last account's row, the total number of columns
        """
        header_row = 3
        cols, current_row = self.create_header_row(parent, header_row)
        for idx, account in enumerate(self.account_table):
            self.dynamic_table_row(parent, current_row, 0, account)
            current_row += 1
        ttk.Label(parent, text="Friendly Name:").grid(row=0, column=1)
        self.input_box = ttk.Entry(parent)
        self.input_box.grid(row=0, column=1)
        ttk.Button(parent, text="Add Account", command=self.add_account_callback).grid(
            row=0, column=2
        )
        ttk.Label(parent, text="Total Liquid Assets").grid(row=0, column=4)
        liquid_colspec = dynamic_item_spec(
            Owner.NONE,
            "Liquid Assets",
            None,
            (self.sum_liquid_assets, self.currency_format),
        )
        self.dynamic_gridded_label(parent, 0, 5, None, liquid_colspec)
        return current_row, cols

    def sum_liquid_assets(self, dummy) -> int:
        """
        Computes the total liquid assets across all accounts monitored, defined as the sum of all Commanders' balance
        plus the sum of all Fleet Carriers' balances.
        :return: total liquid assets for all accounts (int)
        """
        liquid_assets = 0
        for account in self.account_table:
            if not account.reauth_required:
                liquid_assets += int(account.cmdr_data["commander"]["credits"]) + int(
                    account.fc_data["balance"]
                )
        return liquid_assets

    def recreate_main_frame(self) -> None:
        """
        Destroys the frame containing the Label grid array and recreates. Called twice in the process of adapting to
        the number of accounts changing: once to make room for the new (empty except for the cAPI link) row, and again
        after the account data has been populated to actually create the dynamic Labels for that account.

        This method also destroys the capi_buttons and dynamic_labels arrays and creates them from scratch as it was
        easier than determining how to modify them to accommodate the new account(s).
        :return: nothing
        """
        self.frm1.destroy()
        self.capi_buttons = []
        self.dynamic_labels = []
        for account in self.account_table:
            account.reauth_prompted = False
        self.create_main_frame(self.tab_control)

    def add_account_callback(self) -> None:
        """
        This function is executed when the "Add Account" button is pressed.
        :return: Nothing
        """
        if self.input_box.get() == "":
            messagebox.showerror("Error", "Account name must not be blank!")
        is_unique = True
        for account in self.account_table:
            is_unique = self.input_box.get() != account.name
            if not is_unique:
                break

        if is_unique:
            self.account_table.append(
                Account(self.conn, self.log_handler, self.input_box.get())
            )
            self.recreate_main_frame()
        else:
            messagebox.showerror("Error", "Account name must be unique!")

    def remove_account_callback(self, e) -> None:
        """
        Removes the account whose delete label was clicked from both the account table in memory and on disk.
        Destroys everything so account must be re-added and re-authed from scratch.
        :param e: The Label that generated the callback event (i.e. the one that was clicked)
        :return: Nothing
        """
        for item in self.dynamic_labels:
            if item[LABEL] == e.widget:
                account_to_pop = item[ACCOUNT]
                account_to_pop.destroy()
                break
        idx = 0
        for account in self.account_table:
            if account == account_to_pop:
                break
            idx += 1

        self.logger.info(
            "Popping account: "
            + account_to_pop.name
            + ":"
            + self.account_table[idx].name
        )
        self.account_table.pop(idx)
        self.recreate_main_frame()

    @staticmethod
    def passthrough(value) -> object:
        """
        Passes the value through. A default do-nothing post-processor for data that does not require post-processing.
        :param value: The data to (not) be post-processed.
        :return: The data after (no) post-processing.
        """
        return value

    @staticmethod
    def currency_format(value) -> str:
        """
        Formats the number passed in with a comma every three places e.g. thousands, millions, etc.
        :param value: The number to be post-processed.
        :return: The number, formatted as XX,YYY,ZZZ (etc.)
        """
        return "{:0,.0f}".format(float(value))

    @staticmethod
    def hex_decode(value) -> str:
        """
        Decodes a hex-encoded string into plaintext. Used for Fleet Carrier names.
        :param value: The string, hex-encoded.
        :return: The plaintext string
        """
        return bytearray.fromhex(value).decode()

    @staticmethod
    def capi_column(account) -> str:
        """
        Implements the logic to determine what icon to indicate cAPI status.
        :param account: The account whose connection we are indicating.
        :return: The cAPI status icon (emoji).
        """
        return "⚠️" if account.reauth_required else "✅"

    @staticmethod
    def delete_column(account) -> str:
        """
        Returns the "Delete Account" icon (emoji). Simpler to implement static text this way considering how
        uncommon it is.
        :param account: The account we are deleting. Unused here, but architecture requires passing it.
        :return: The X emoji.
        """
        return "❌"

    @staticmethod
    def calculate_tonnage(fc_data) -> int:
        """
        Adds up the total cargo loaded on the fleet carrier described by fc_data.
        :param fc_data: the fleet carrier's data object
        :return: the total cargo loaded.
        """
        return fc_data["cargoNotForSale"] + fc_data["cargoForSale"]

    @staticmethod
    def ladder_display(system) -> str:
        """
        Returns a label showing the ladder position when a ladder system is detected.
        :param system: The system name
        :return: the formatted system name, with N label where appropriate
        """
        if system in LADDER:
            return LADDER[system]
        else:
            return ""

    @staticmethod
    def blank_table_row(parent, row, account, colstart, number_cols) -> None:
        """
        Creates a blank data row, used when accounts are added but not fully-authorized yet.
        :param parent: The GUI element that contains the Label grid array
        :param row: The row number in the Label grid array this blank row should be
        :param account: The account to which this data belongs
        :param colstart: The column where we start populating data
        :param number_cols: The number of blank columns to create
        :return: Nothing
        """
        ttk.Label(parent, text=account.name).grid(row=row, column=colstart)
        colstart += 1
        for i in range(colstart, number_cols + 1):
            ttk.Label(parent, text="-").grid(row=row, column=i)

    def count_ready_accounts(self) -> int:
        """
        Returns the number of accounts that are currently authorized through cAPI
        :return: number of accounts
        """
        number_ready = 0
        for account in self.account_table:
            if not account.reauth_required:
                number_ready += 1
        return number_ready

    def generate_capi_uri(self, e) -> bool:
        """
        Generates the unique (re)auth URI for the account whose cAPI label we are currently processing. Required to bind
        the button-click event. Acts as the click callback.
        :param e: The Label that we are currently updating.
        :return: not really relevant-- the action is opening the browser.
        """
        for item in self.dynamic_labels:
            if item[LABEL] == e.widget:
                return webbrowser.open_new(item[ACCOUNT].get("auth_uri"))

    @staticmethod
    def ghost_orders(sales) -> str:
        """
        Returns a comma-separated list of open buy orders whose quantity is zero ("ghost orders")
        :param sales: The market data for the carrier we are working on
        :return: the list of ghost sales
        """
        orders = ""
        for sale in sales:
            if int(sale["stock"]) == 0:
                orders = orders + str.title(sale["name"]) + ","
        if len(orders) == 0:
            orders = "None"
        else:
            orders = orders[:-1]
        return orders
