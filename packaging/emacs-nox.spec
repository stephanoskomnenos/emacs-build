# emacs_version is supplied by scripts/linux/rpm.py from the locked snapshot.
%global debug_package %{nil}
%global _build_id_links none
# Preserve the already tested executable and its matching portable dump.
# Distribution postprocessing (strip, byte compilation, etc.) must not alter it.
%global __os_install_post %{nil}
# Lisp data includes example scripts whose interpreters are not runtime needs.
%global __requires_exclude_from ^/opt/emacs-nox/share/.*$
%global __provides_exclude_from ^/opt/emacs-nox/.*$

Name:           emacs-nox
Epoch:          1
Version:        %{emacs_version}
Release:        1
Summary:        Terminal GNU Emacs with static third-party libraries
License:        GPL-3.0-or-later
URL:            https://www.gnu.org/software/emacs/
Source0:        emacs-%{version}-linux-x86-64-v3.tar.zst
ExclusiveArch:  x86_64
Requires:       glibc%{?_isa} >= 2.41
Requires:       coreutils
Requires(posttrans): coreutils
Requires:       ncurses-base
Requires:       ca-certificates
Provides:       emacs = %{epoch}:%{version}-%{release}
Provides:       emacsclient = %{epoch}:%{version}-%{release}
Conflicts:      emacs
Conflicts:      emacs-nw
Conflicts:      emacs-common
Conflicts:      emacs-lucid
Conflicts:      emacs-pgtk
Conflicts:      emacsclient

%description
GNU Emacs for terminals, built with Clang, ThinLTO and PGO and without native compilation.
Foundation libraries are statically linked;
glibc, terminfo, CA certificates, modules and language grammars use the host.
Component license notices are included under the installation's licenses tree.

Installs under /opt/emacs-nox and provides the standard emacs and
emacsclient commands. Replaces distribution Emacs packages when installed
with dnf --allowerasing.
This spec packages the tested portable binary; compilation recipes and all
source inputs are distributed in the separate companion source archive.

%prep
%setup -q -n emacs-%{version}-linux-x86-64-v3

%build
# Emacs and its libraries were built and tested in the Debian compiler image.

%install
mkdir -p %{buildroot}/opt/emacs-nox %{buildroot}%{_bindir}
cp -a . %{buildroot}/opt/emacs-nox/
ln -s /opt/emacs-nox/bin/emacs %{buildroot}%{_bindir}/emacs
ln -s /opt/emacs-nox/bin/emacsclient %{buildroot}%{_bindir}/emacsclient

%posttrans
# The removed Fedora package deregisters alternatives during its uninstall and
# can unlink /usr/bin/emacs after our payload was installed. Restore both owned
# entry points only after all packages in the replacement transaction finish.
ln -sfn /opt/emacs-nox/bin/emacs %{_bindir}/emacs
ln -sfn /opt/emacs-nox/bin/emacsclient %{_bindir}/emacsclient

%files
%defattr(-,root,root,-)
%{_bindir}/emacs
%{_bindir}/emacsclient
/opt/emacs-nox
