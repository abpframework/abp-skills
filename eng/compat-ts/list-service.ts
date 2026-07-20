// Compile-smoke for skill: abp-ui/build-angular-lists-and-forms
// Exercises ListService query state, hookToQuery -> PagedResultDto, refresh, and
// requestStatus$/totalCount (the non-deprecated members the skill teaches).
import { ListService, PagedResultDto } from '@abp/ng.core';
import { of, type Observable } from 'rxjs';

interface BookDto {
  id: string;
  name: string;
}

export function exerciseListService(
  list: ListService,
): Observable<PagedResultDto<BookDto>> {
  list.maxResultCount = 20;
  list.page = 0;
  list.filter = 'abc';
  list.sortKey = 'name';
  list.sortOrder = 'asc';

  const requestStatus$: Observable<unknown> = list.requestStatus$;

  const stream$ = list.hookToQuery<BookDto>(() =>
    of<PagedResultDto<BookDto>>({ items: [], totalCount: 0 }),
  );

  list.get();
  list.getWithoutPageReset();
  const total: number = list.totalCount;

  void requestStatus$;
  void total;
  return stream$;
}
