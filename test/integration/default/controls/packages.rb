# frozen_string_literal: true

control 'incus.package.install' do
  title 'The required package should be installed'

  describe package('incus') do
    it { should be_installed }
  end
end
