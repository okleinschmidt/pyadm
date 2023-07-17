# pyadm - Swiss Army Knife for Engineers and Administrators

**pyadm** is a versatile command-line tool designed as a Swiss Army Knife for engineers and administrators.\
It provides modular functionality to perform various tasks efficiently. 

**Currently, the only available module is `ldap`, which enables LDAP-related operations.**

## Installation

To install `pyadm`, use the following command (soon!):

```shell
pip install pyadm-toolkit
```
## Usage
The general command structure for pyadm is as follows:
```shell
pyadm MODULE SUBCOMMAND [OPTIONS]
```
To use the LDAP module, execute the pyadm ldap command followed by the desired subcommand to perform specific LDAP operations.

## LDAP Module
The LDAP module within pyadm allows you to interact with LDAP servers and perform common operations, such as retrieving user information, showing group associations, and displaying group members.

### Examples
* Retrieve information for a user in the LDAP directory:
  ```shell
  pyadm ldap user USERNAME
  ```
* Show groups associated with a user in the LDAP directory:
  ```shell
  pyadm ldap groups USERNAME
  ```
* Show members of a group in the LDAP directory:
  ```shell
  pyadm ldap members GROUP_CN
  ```
For more information on each subcommand, you can use the --help option, as shown in the examples below:
```shell
pyadm ldap user --help
pyadm ldap groups --help
pyadm ldap members --hel
```

## Configuration
The pyadm tool allows you to customize its behavior through a configuration file. By default, the configuration file is located at `~/.config/pyadm/pyadm.conf`.

To use a custom configuration file, create a file in the following format:
```ini
[LDAP]
server = ldaps://dc.example.org
base_dn = dc=example,dc=org
bind_username = administrator@example.org
bind_password = s3cr3t-p455w0rd!
```
Specify the desired values for the LDAP server, base DN, bind username, and bind password in the configuration file.

## Contributing
Contributions are welcome! If you encounter any issues, have suggestions, or would like to add new features, please submit an issue or a pull request.

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).\
Feel free to copy and use this markdown source as needed for your `README.md` file.
