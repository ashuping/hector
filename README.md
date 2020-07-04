# Hector
## A discord bot for RP servers
Roleplaying servers on discord tend to have an overabundance of RP channels, especially when those servers use one channel per location. While this makes sense, it can clutter up the channel list, forcing players to sift through a long list to find the area they want.

Hector manages this clutter by moving channels elsewhere when not in use. Hector is designed to be highly-configurable by server administrators, with a robust permissions system using discord roles to allow fine-grained control of user actions.

## Features
* Guilds can manage large numbers of channels in a quick and user-friendly manner, allowing users to easily find channels while hiding them away when not in use.
* Administrators can exert fine-grained control over user permissions using roles.
  * Roles obey a hierarchy based on their position in the role list: higher roles can override lower roles.
* Channels follow the permissions of their categories - users can be prevented from seeing or sending messages to inactive channels with the inactive category's settings.

## Summary
### Interface
By default, Hector responds to commands prefixed with a pipe character (`|`). This can be changed on a per-instance basis, but not on a per-guild basis. When mentioned, Hector will respond to the user asking them to use `|help` for a list of commands.

Most messages sent by Hector will have a trash-can reaction added. The user who invoked the command that caused the message, as well as any user with the 'manage messages' permission in the relevant channel, can click the trash can to have Hector delete the message in question. Hector will not respond to other users or reactions.

When Hector encounters an error, it replies with an embed explaining the error. Clicking the star reaction will cause Hector to edit the message to show a stack-trace for the error. When asking for help with an error, please copy over this stack trace.

Certain other messages will also ask the user to click a reaction button to continue or choose an option. In most cases, Hector will only respond to reactions from the user who sent the relevant command.

### Regions and Channels
Hector uses "Regions" to manage channels. A region encompasses a channel and the name, description, and active-category associated with it. Regions can be active or inactive - active regions are kept in their active categories, while inactive regions are moved to the guild's inactive category. A region's name, description, and status are shown in the region's channel topic.

The status of a region can be changed with the `|open` and `|close` commands. A region's active category can be modified with the `|move` command, and its description can be changed with the `|describe` command.

Regions can be created with new channels by using `|open`, or converted from existing channels with `|makeregion`. Regions created by `|open` default to the category in which the `|open` command was invoked, while `|makeregion`-created regions use the same category as the channel from which they were converted.

Regions can be moved, either during cretation with `|open`, or later with `|move`. However, in order to move a region to a new category, a user must have the permissions required to re-order the channel and change its category.

### Permissions
Hector's permission system associates individual permissions with roles in a configurable way. Roles are managed in a hierarchy - roles which are higher on the guild's list can override those which are lower. If a user has multiple roles with Hector permissions attached, they will usually have all permissions associated with both roles. However, if the higher-priority role is set to *deny* a permission (using the `|perms deny` command or certain permission presets), the user will not have the permission even if the lower-priority role grants it. 

The default is to neither grant nor deny a permission, and users do not have a permission unless it is granted by one of their roles.

## Command reference
### Server settings
`|rpset inactive` (requires `manage` permission)
Sets the guild-wide inactive channel category to the one in which this command is run.

### Region creation, opening, and closing
`|open [name]` (requires `open` permission)
Opens the region specified by `[name]`. When run without the `[name]` parameter, Hector will attempt to open the region associated with the current channel.

If `[name]` is specified, `[name]` does not match a currently-known region, and the calling user has the `create` permission, Hector will offer to create the region. Regions created in this way will be added to the same category as channel in which the `|open` command was invoked. Users are given the option to move the new channel to a different category - note that this requires the user have permissions to change the channel's category. Users who do not have this permission are advised to run the `|open` command from a channel in the same category as they wish the new region to be active in, or to ask for assistance from a moderator who can move the channel.

Once the channel has been created, users must use the `|move` command to change its category.

`|makeregion <name>` (requires `convert` permission)
Converts the current channel into a region with a name specified by `<name>`. The region description will be set to the channel's current topic.

`|close [name]` (requires `close` permission)
Closes the region specified by `[name]`. When run without the `[name]` parameter, Hector will attempt to close the region associated with the current channel.

`|list`
Outputs a list of regions available on the current server.

### Region modification
`|move [channel-name]` (requires `move` permission)
Allows the user to set a region's active category. When run without `[channel-name]`, the command defaults to the region associated with the current channel. Administrators should note that, in order to use this command, a user must also be able to re-order the channel.

`|describe <new description>` (requires `describe` permission)
Sets the description for the region associated with the current channel to `<new description>`.

`|unmake <region name>` (requires `unmake` permission)
Removes the region named `<region name>`. Note that this does not remove the channel associated with this region; however, the channel is no longer managed by Hector.

### Permissions
`|myperms [user]`
Shows a user's permissions. If no `[user]` is provided, Hector will default to the user who ran the command.

`|perms grant <role name> <permission names...>` (requires `manage` permission)
Grants the permissions specified by `<permission names>` to the role specified by `<role name>`. Multiple permissions can be granted at once with this command - separate permission names with spaces.

`|perms deny <role name> <permission names...>` (requires `manage` permission)
Denies the permissions specified by `<permission names>` to the role specified by `<role name>`. Multiple permissions can be denied at once with this command - separate permission names with spaces.

`|perms clear <role name> <permission names...>` (requires `manage` permission)
Clears the permissions specified by `<permission names>` to the role specified by `<role name>`. Note that this is NOT the same as denying those permissions: cleared permissions will not override permissions granted by lower roles. Multiple permissions can be cleared at once with this command - separate permission names with spaces.

`|perms listperms` (requires `manage` permission)
Lists all permissions. This can be used to find permission names for use in `|perms grant` or `|perms deny`.

`|perms preset <preset name>` (only usable by guild administrators)
Overrides all current Hector permissions with a built-in preset. This can be useful when setting up Hector on a new server, as Hector will automatically create and set up permissions for the roles associated with the preset. Use with caution.

`|perms listpresets` (only usable by guild administrators)
List the current built-in presets, along with roles and permissions, for use with the `|perms preset` command. Higher roles have higher priority, and the '*' role refers to permissions granted or denied globally.

### Miscellaneous
`|help [topic]`
Shows the help menu.

`|version`
Shows Hector's current version.

`|invite`
Shows a link which you can use to invite Hector to your server.

`|ping`
Used mainly to verify that Hector is online. Responds `Pong, <user>`, where `<user>` is the name of the user who ran the command.

`|zyn`
Marp.

## Guild setup
I am hosting a bot running the stable branch of Hector. It can be invited to your guild [here](https://discordapp.com/api/oauth2/authorize?client_id=473652354680356885&scope=bot&permissions=469838928).

Once Hector has joined your server, the following steps are requried for setup:
1) A server administrator should set up the permission system. A number of presets have been added to make this process simpler - run `|perms listpresets` to see a list of possible presets and `|perms preset presetnamehere` to choose a preset. Hector will create the necessary roles and permissions automatically.
1) Alternatively, use the `|perms listperms` command to see a list of permissions, and grant/deny them manually using `|perms grant rolenamehere permissionnamehere` and `|perms deny rolenamehere permissionnamehere`.
1) Once permissions have been set up, choose the category where inactive region channels are stored by running `|rpset inactive` in any channel within the desired category. Hector will sync channel permissions with the inactive category when a region is closed, so if you would like to hide or deny message-sending permissions for inactive channels, you should set up those permissions on the inactive category.
1) To create a new region, run `|open regionname`. If you have the `create` permission, you will be prompted to create the new region. Note that region names do not follow the same restrictions as discord channels - spaces, capitalization, and special characters are acceptable, and will show up as such in the region list and channel topic. Hector will set the region's channel name to a sanitized version of the region name which follows discord's restrictions.
1) If your server already has RP channels set up, they can be converted to Hector regions easily. Simply run `|makeregion regionname` within the desired channel. Note that this requries the `convert` permission.
1) All users can run `|list` to view a list of regions.

## Host an Instance
To host an instance of Hector, you need a system with Python 3.8 or higher. Importantly, **you also need libsqlite3 version 3.24.0 or higher**. Installation is as follows:
1) Clone this repository into its own folder
1) Install required modules with `python3.8 -m pip install -r requirements`
1) Rename the file `bot_info.json.skel` to `.bot_info.json`
1) In the file `.bot_info.json`, replace the text `INSERT YOUR BOT TOKEN HERE!` with your bot token
1) Optionally, change the bot description or command prefix to your liking
1) Start Hector with `python3.8 hector.py`
