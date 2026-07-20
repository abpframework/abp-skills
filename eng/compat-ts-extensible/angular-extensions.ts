// Compile-smoke for skill: abp-ui/extend-angular-module-ui
// Exercises the @abp/ng.components/extensible API the skill teaches: the item factories
// (EntityAction / EntityProp / FormProp), ePropType, and the linked-list mutators
// (addTail / addAfter / addByIndex / dropByIndex). Lives in its own Angular-20 workspace
// because @abp/ng.components transitively needs ngx-datatable, which caps at Angular 20.
import {
  EntityAction,
  EntityActionList,
  EntityProp,
  EntityPropList,
  FormProp,
  FormPropList,
  ePropType,
} from '@abp/ng.components/extensible';

interface SampleDto {
  id: string;
  name: string;
}

export function contributeEntityAction(actionList: EntityActionList<SampleDto>): void {
  actionList.addTail(
    new EntityAction<SampleDto>({ text: 'Say Hi', action: data => void data.record.name }),
  );
}

export function contributeColumn(propList: EntityPropList<SampleDto>): void {
  propList.addAfter(
    new EntityProp<SampleDto>({ type: ePropType.String, name: 'name', displayName: '::Name', sortable: true }),
    'id',
    (value, name) => value.name === name,
  );
}

export function contributeFormField(propList: FormPropList<SampleDto>): void {
  const field = new FormProp<SampleDto>({ type: ePropType.Date, name: 'birthday', displayName: '::Birthday' });
  propList.addByIndex(field, 2);
  // "patch" pattern: drop then re-add (there is no patch method)
  const node = propList.dropByIndex(2);
  if (node) {
    propList.addByIndex(new FormProp<SampleDto>({ ...node.value }), 2);
  }
}
