// Compile-smoke for skill: abp-testing/test-angular-ui
// Exercises the ABP Angular testing module + body-cleanup helpers the skill teaches.
import { clearPage, CoreTestingModule, wait } from '@abp/ng.core/testing';
import type { ComponentFixture } from '@angular/core/testing';
import type { ModuleWithProviders } from '@angular/core';

export function exerciseAngularTesting<T>(fixture: ComponentFixture<T>): void {
  const mod: ModuleWithProviders<CoreTestingModule> = CoreTestingModule.withConfig({
    baseHref: '/',
    listQueryDebounceTime: 0,
  });

  clearPage(fixture);
  void wait(fixture, 0);
  void mod;
}
