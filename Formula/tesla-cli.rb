class TeslaCli < Formula
  include Language::Python::Virtualenv

  desc "Tesla CLI — order tracking, vehicle control, dossier, and live telemetry"
  homepage "https://github.com/dacrypt/tesla"
  url "https://files.pythonhosted.org/packages/source/t/tesla-cli/tesla_cli-0.4.0.tar.gz"
  # sha256 will be filled in automatically after PyPI release
  license "MIT"

  head "https://github.com/dacrypt/tesla.git", branch: "main"

  depends_on "python@3.12"

  resource "typer" do
    url "https://files.pythonhosted.org/packages/source/t/typer/typer-0.15.3.tar.gz"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.28.1.tar.gz"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.11.1.tar.gz"
  end

  resource "pydantic-settings" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic_settings/pydantic_settings-2.7.1.tar.gz"
  end

  resource "keyring" do
    url "https://files.pythonhosted.org/packages/source/k/keyring/keyring-25.6.0.tar.gz"
  end

  resource "apprise" do
    url "https://files.pythonhosted.org/packages/source/a/apprise/apprise-1.9.0.tar.gz"
  end

  resource "pyjwt" do
    url "https://files.pythonhosted.org/packages/source/p/pyjwt/pyjwt-2.10.1.tar.gz"
  end

  resource "tomli-w" do
    url "https://files.pythonhosted.org/packages/source/t/tomli_w/tomli_w-1.1.0.tar.gz"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/tesla --version")
    assert_match version.to_s, output
  end
end
