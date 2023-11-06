# EDFleetTracker

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
--- 

Elite Dangerous Fleet Tracker (EDFT) is a standalone desktop application to help those who operate large carrier fleets (be that Squadrons, Trade Federations, or particularly-overachieving CMDRs) track the position and status of their various carriers. EDFT strives to be a single pane of glass interface where relevant information about the entire fleet is visible at a glance without the need to start the game.

A natural evolution of manually-updated spreadsheets, EDFT automates the collection of relevant stats and data from Frontier's Companion API (cAPI) so that you can immediately focus on the carriers that need attention, and not waste time on the tedium of updating tracking sheets.

For the moment, EDFT is released for Windows only. There is nothing inherently Windows-specific about the day-to-day operation, but the cAPI authentication process needs some work to enable cross-platform operation.

## Installation and Usage

### Installation
Windows Installers have been provided in [Releases](https://github.com/axleantilles/EDFleetTracker/releases). To handle cAPI authentication, EDFT needs to register a custom URI handler in the Registry. Unfortunately, this means the installer requires elevation to Administrator privileges. However, the application itself does not—once the handler is registered, the application can use it with normal user privileges.

Due to restrictions imposed by Frontier, the binaries provided here are the only way to obtain a working copy of the application—developers are forbidden from sharing their API credentials, so attempts to run the Python code directly will fail. Anyone willing to obtain their own API credentials is welcome to reach out to me for assistance in integrating them.


### Usage

After first launch, the user will be presented with a blank table area, an input box, and an "Add Account" button.

#### To add a new account:
1. Give the new account a short nickname, and input into the blank text box. (This is helpful when adding more than one account because details cannot be fetched from cAPI until permission is given, which is done later—account nicknames help you keep the table rows straight in the absence of real data.)
2. Click "Add Account," and a new blank row will appear at the bottom of the table.
3. The new row will have an exclamation mark icon in the "cAPI" column. Clicking this will open your browser to the Frontier authentication page.
4. Log in and authorize EDFT for the new account. Allow the helper application to process edft:// links if your browser or Windows prompts you.
5. After 2-5 seconds, your new account's data should populate in EDFT and the cAPI icon should turn into a check mark.

**Note**: Roughly once a month, Frontier requires explicit reauthorization. When this happens, the cAPI icon beside the account will again become an exclamation point. Follow steps 3-5 above, clicking the exclamation mark next to the account you wish to update, and you will be good for another month.

#### To delete an account:
Click the "X" in the far left column. **WARNING:** There is no confirmation for this, and once done, the entire process above must be repeated to re-add the account.

#### What are "Ghost Sells?"
Ghost Sells are an annoying bug in the way carrier markets behave. It is possible to have an open buy order with a quantity of zero units. This buy order will not show up in the Market screen, but will be counted in your "Active Imports" stat. Most CMDRs want to eliminate these to have accurate import/export numbers. EDFT shows a comma-separated list of Commodities for which your carrier has these "Ghost Sells" so you can go in and remove them by cycling the "Trade this commodity" button in the Commodity Trading screen of your Carrier Admin page.

#### How is Tonnage calculated?
Tonnage is the sum of all cargo loaded onto your carrier (whether it is for sale or not), and _does not_ include the weight of any installed services.

## Known Issues

- When adding a new account, once the authentication process is complete, the main EDFT window becomes briefly unresponsive as the data for that new account is loaded from cAPI. Expect a 2-5 second delay after completing authentication for each new account.
- UI is _ugly_. I know.

## License


MIT

## Contributing

Pull requests are welcome. Please ensure that your code matches the Black code style _prior_ to submitting a PR.
