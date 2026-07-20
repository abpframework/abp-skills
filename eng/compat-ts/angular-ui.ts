import {
  type ABP,
  ConfigStateService,
  eLayoutType,
  LocalizationService,
  PermissionService,
  permissionGuard,
  RoutesService,
} from '@abp/ng.core';
import type { CanActivateFn } from '@angular/router';
import type { Observable } from 'rxjs';

export function exerciseAngularUi(
  configState: ConfigStateService,
  permissions: PermissionService,
  routes: RoutesService,
  localization: LocalizationService,
): void {
  const auth = configState.getOne('auth');
  const currentUser = configState.getDeep('currentUser');
  const authChanges = configState.getOne$('auth');
  const canCreate: boolean = permissions.getGrantedPolicy('BookStore.Books.Create');
  const canEdit$: Observable<boolean> = permissions.getGrantedPolicy$('BookStore.Books.Edit');

  const route: ABP.Route = {
    path: '/books',
    name: '::Menu:Books',
    iconClass: 'fas fa-book',
    order: 101,
    layout: eLayoutType.application,
    requiredPolicy: 'BookStore.Books',
  };

  routes.add([route]);

  const title: string = localization.instant('::Menu:Books');
  const title$: Observable<string> = localization.get('::Menu:Books');
  const guard: CanActivateFn = permissionGuard;

  void auth;
  void currentUser;
  void authChanges;
  void canCreate;
  void canEdit$;
  void title;
  void title$;
  void guard;
}
