# Nylas Sync Engine


The Nylas Sync Engine provides a RESTful API on top of a powerful email sync platform, making it easy to build apps on top of email. See the [full API documentation](https://www.nylas.com/docs/api#overview) for more details.



### Installation and Setup

1. Install the latest versions of [VirtualBox](https://www.virtualbox.org/wiki/Downloads) and [Install Vagrant](http://www.vagrantup.com/downloads.html).

2. `git clone git@github.com:inboxapp/inbox.git`

3. `cd inbox`

4. `vagrant up`

    Feel free to check out the `Vagrantfile` while this starts up. It creates a host-only network for the VM at `192.168.10.200`.

5. `vagrant ssh`

6. `cd /vagrant`

7. `bin/inbox-start`

And _voilà_! Auth an account via the commandline to start syncing:

    bin/inbox-auth ben.bitdiddle1861@gmail.com


## Production Support

We provide a fully manged and supported version of the Nylas sync engine for production apps. Read more at https://nylas.com


## Pull Requests

We'd love your help making Nylas better! Please sign-up for a [developer account](https://nylas.com/register) for project updates and the latest news. Feel free to create issues or pull requests to start discussions.

We require all authors sign our [Contributor License Agreement](https://www.nylas.com/cla.html) when submitting pull requests. (It's similar to other projects, like NodeJS or Meteor.)


## License

This code is free software, licensed under the The GNU Affero General Public License (AGPL). See the `LICENSE` file for more details.
